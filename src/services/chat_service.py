from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import Conversation, Message, User
from src.schemas.chat import MessageCreate, ConversationCreate
from src.agent.workflow import agent_executor
from langchain_core.messages import HumanMessage
import uuid
import json

async def create_conversation(db: AsyncSession, user_id: uuid.UUID, title: str):
    db_conversation = Conversation(user_id=user_id, title=title)
    db.add(db_conversation)
    await db.commit()
    await db.refresh(db_conversation)
    return db_conversation

async def get_user_conversations(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()))
    return result.scalars().all()

async def delete_conversation(db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    conversation = result.scalars().first()
    if not conversation:
        raise ValueError("Conversation not found or unauthorized")
    
    await db.delete(conversation)
    await db.commit()
    return True

async def process_chat_message(db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID, msg: MessageCreate):
    # Verify conversation exists and belongs to user
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    conversation = result.scalars().first()
    if not conversation:
        raise ValueError("Conversation not found or unauthorized")

    # Save Human Message
    human_msg_db = Message(conversation_id=conversation_id, role="user", content=msg.content)
    db.add(human_msg_db)
    await db.commit()

    # Retrieve history
    history_result = await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    history_msgs = history_result.scalars().all()
    
    # Format for LangGraph
    langchain_messages = []
    for h in history_msgs:
        if h.role == "user":
            langchain_messages.append(HumanMessage(content=h.content))
        elif h.role == "assistant":
            # For simplicity, we append it as AIMessage
            from langchain_core.messages import AIMessage
            langchain_messages.append(AIMessage(content=h.content))
            
    # Run Agent
    state = {
        "messages": langchain_messages,
        "model_name": msg.model,
        "user_id": str(user_id),
        "conversation_id": str(conversation_id)
    }
    
    response_state = await agent_executor.ainvoke(
        state,
        config={"configurable": {"user_id": str(user_id), "conversation_id": str(conversation_id)}}
    )
    ai_response = response_state["messages"][-1].content
    
    # Save AI Message
    ai_msg_db = Message(conversation_id=conversation_id, role="assistant", content=ai_response)
    db.add(ai_msg_db)
    await db.commit()
    await db.refresh(ai_msg_db)
    
    return ai_msg_db

async def stream_chat_message(db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID, msg: MessageCreate):
    # Verify conversation exists and belongs to user
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    conversation = result.scalars().first()
    if not conversation:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Conversation not found or unauthorized'})}\n\n"
        return

    # Save Human Message
    human_msg_db = Message(conversation_id=conversation_id, role="user", content=msg.content)
    db.add(human_msg_db)
    await db.commit()

    # Retrieve history
    history_result = await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    history_msgs = history_result.scalars().all()
    
    # Format for LangGraph
    langchain_messages = []
    for h in history_msgs:
        if h.role == "user":
            langchain_messages.append(HumanMessage(content=h.content))
        elif h.role == "assistant":
            from langchain_core.messages import AIMessage
            langchain_messages.append(AIMessage(content=h.content))
            
    # Run Agent
    state = {
        "messages": langchain_messages,
        "model_name": msg.model,
        "user_id": str(user_id),
        "conversation_id": str(conversation_id)
    }
    
    config = {"configurable": {"user_id": str(user_id), "conversation_id": str(conversation_id)}}
    ai_response_chunks = []
    
    try:
        async for event in agent_executor.astream_events(state, config=config, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content and isinstance(content, str):
                    ai_response_chunks.append(content)
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
            elif kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': event['name'], 'input': event['data'].get('input')})}\n\n"
            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': event['name']})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        return
        
    ai_response_full = "".join(ai_response_chunks)
    
    # Save AI Message
    if ai_response_full:
        ai_msg_db = Message(conversation_id=conversation_id, role="assistant", content=ai_response_full)
        db.add(ai_msg_db)
        await db.commit()

