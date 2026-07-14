from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import Conversation, Message
from src.schemas.chat import MessageCreate
from src.agent.workflow import agent_executor
from langchain_core.messages import AIMessage, HumanMessage
import uuid
import json
from typing import Any


def message_text(message: Any) -> str:
    """Return the text portion of a LangChain message or streamed chunk."""
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text

    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


async def ensure_conversation_access(
    db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conversation = result.scalars().first()
    if not conversation:
        raise ValueError("Conversation not found or unauthorized")
    return conversation


async def get_langchain_history(db: AsyncSession, conversation_id: uuid.UUID):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return [
        HumanMessage(content=message.content)
        if message.role == "user"
        else AIMessage(content=message.content)
        for message in result.scalars()
        if message.role in {"user", "assistant"}
    ]

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
    conversation = await ensure_conversation_access(db, user_id, conversation_id)
    
    await db.delete(conversation)
    await db.commit()
    return True

async def process_chat_message(db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID, msg: MessageCreate):
    await ensure_conversation_access(db, user_id, conversation_id)

    # Save Human Message
    human_msg_db = Message(conversation_id=conversation_id, role="user", content=msg.content)
    db.add(human_msg_db)
    await db.commit()

    # Retrieve history
    langchain_messages = await get_langchain_history(db, conversation_id)
            
    # Run Agent
    state = {
        "messages": langchain_messages,
        "model_name": msg.model,
        "user_id": str(user_id),
        "conversation_id": str(conversation_id),
        "enable_web_search": msg.enable_web_search,
        "generate_document": msg.generate_document,
    }
    
    response_state = await agent_executor.ainvoke(
        state,
        config={"configurable": {"user_id": str(user_id), "conversation_id": str(conversation_id)}}
    )
    ai_response = message_text(response_state["messages"][-1])
    
    # Save AI Message
    ai_msg_db = Message(conversation_id=conversation_id, role="assistant", content=ai_response)
    db.add(ai_msg_db)
    await db.commit()
    await db.refresh(ai_msg_db)
    
    return ai_msg_db

async def stream_chat_message(db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID, msg: MessageCreate):
    # Verify conversation exists and belongs to user
    try:
        await ensure_conversation_access(db, user_id, conversation_id)
    except ValueError:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Conversation not found or unauthorized'})}\n\n"
        return

    # Save Human Message
    human_msg_db = Message(conversation_id=conversation_id, role="user", content=msg.content)
    db.add(human_msg_db)
    await db.commit()

    # Retrieve history
    langchain_messages = await get_langchain_history(db, conversation_id)
            
    # Run Agent
    state = {
        "messages": langchain_messages,
        "model_name": msg.model,
        "user_id": str(user_id),
        "conversation_id": str(conversation_id),
        "enable_web_search": msg.enable_web_search,
        "generate_document": msg.generate_document,
    }
    
    config = {"configurable": {"user_id": str(user_id), "conversation_id": str(conversation_id)}}
    ai_response_chunks = []
    final_state = None
    
    try:
        async for event in agent_executor.astream_events(state, config=config, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                if "router" not in event.get("tags", []):
                    content = message_text(event["data"]["chunk"])
                    if content:
                        ai_response_chunks.append(content)
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                # Capture the final graph output state
                final_state = event["data"].get("output")
            elif kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': event['name'], 'input': event['data'].get('input')})}\n\n"
            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': event['name']})}\n\n"
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Unable to process the message'})}\n\n"
        return
        
    # Build the full response string.
    # Primary: join streamed tokens.
    # Fallback: extract from final graph state (handles cases where supervisor
    #           synthesizes a ToolMessage result without streaming).
    ai_response_full = "".join(ai_response_chunks)
    if not ai_response_full and final_state:
        from langchain_core.messages import AIMessage as AIMsg
        msgs = final_state.get("messages", [])
        if msgs and isinstance(msgs[-1], AIMsg):
            ai_response_full = message_text(msgs[-1])
            # Yield the full content as a single token so the client receives it
            if ai_response_full:
                yield f"data: {json.dumps({'type': 'token', 'content': ai_response_full})}\n\n"
    
    # Save AI Message
    if ai_response_full:
        ai_msg_db = Message(conversation_id=conversation_id, role="assistant", content=ai_response_full)
        db.add(ai_msg_db)
        await db.commit()

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
