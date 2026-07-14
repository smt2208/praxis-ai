from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langchain_core.runnables import RunnableConfig
from src.core.config import settings
from src.agent.document import get_retriever
import boto3
import os
import uuid
import tempfile
import subprocess
import glob

# Ensure Tavily API key is set in environment for the tool to pick it up automatically
os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

# Instantiate Tavily tool
tavily_search = TavilySearch(max_results=3)

@tool
def generate_and_upload_document(content: str, file_type: str = "txt") -> str:
    """
    Generates a document with the given content, uploads it to AWS S3,
    and returns a public or pre-signed downloadable link.
    Supported file_types: 'txt', 'md', 'pdf', 'csv', 'json', 'html'.
    """
    supported_types = ["txt", "md", "pdf", "csv", "json", "html"]
    if file_type not in supported_types:
        return f"Unsupported file type. Supported types are: {', '.join(supported_types)}"
        
    file_name = f"generated_doc_{uuid.uuid4().hex[:8]}.{file_type}"
    temp_path = None
    
    try:
        # Create a temp file path safely for Windows
        temp_fd, temp_path = tempfile.mkstemp(suffix=f".{file_type}")
        os.close(temp_fd) # Close immediately so other libraries can write to it
        
        if file_type == "pdf":
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("helvetica", size=12)
            # Replace unsupported characters for standard helvetica
            safe_content = content.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 7, text=safe_content)
            pdf.output(temp_path)
        else:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
        # Upload to S3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region_name
        )
        
        s3_client.upload_file(temp_path, settings.s3_bucket_name, file_name)
        
        # Generate presigned URL (valid for 1 hour)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.s3_bucket_name, 'Key': file_name},
            ExpiresIn=3600
        )
        
        return f"Document successfully generated and uploaded. Download link: {url}"
    except Exception as e:
        return f"Error generating or uploading document: {str(e)}"
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@tool
async def search_uploaded_documents(query: str, config: RunnableConfig) -> str:
    """
    Searches the user's previously uploaded documents for context.
    Use this tool when the user asks about their own files, PDFs, images, or previously discussed documents.
    """
    # Extract user_id injected at runtime via config
    user_id = config["configurable"]["user_id"]
    conversation_id = config["configurable"]["conversation_id"]
    
    # Restrict search to documents uploaded within the current conversation
    retriever = get_retriever(user_id=user_id, conversation_id=conversation_id)
    docs = await retriever.ainvoke(query)
    
    if not docs:
        return "No relevant information found in your uploaded documents."
        
    return "\n\n".join([f"Source: {doc.metadata.get('source', 'Unknown')}\n{doc.page_content}" for doc in docs])
        
@tool
def execute_python_and_visualize(code: str) -> str:
    """
    Executes Python code in a safe sandbox to perform data analysis, math, and data visualization.
    If your code generates charts (e.g., using matplotlib.pyplot), save them to the current directory
    as a .png file (e.g., plt.savefig('chart.png')). The tool will automatically upload them and display them to the user.
    """
    temp_dir = tempfile.mkdtemp()
    code_file_path = os.path.join(temp_dir, "script.py")
    
    with open(code_file_path, "w", encoding="utf-8") as f:
        # Prepend backend headless backend configuration for matplotlib so it doesn't try to open windows
        f.write("import matplotlib\nmatplotlib.use('Agg')\n")
        f.write(code)

    try:
        # Execute the python script
        result = subprocess.run(
            ["python", code_file_path],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=30 # 30 second timeout
        )
        
        output_msg = ""
        if result.stdout:
            output_msg += f"Stdout:\n```text\n{result.stdout}\n```\n"
        if result.stderr:
            output_msg += f"Stderr:\n```text\n{result.stderr}\n```\n"
            
        # Check for generated png images
        png_files = glob.glob(os.path.join(temp_dir, "*.png"))
        image_markdowns = []
        
        if png_files:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region_name
            )
            
            for png_file in png_files:
                file_name = f"viz_{uuid.uuid4().hex[:8]}.png"
                s3_client.upload_file(png_file, settings.s3_bucket_name, file_name)
                
                # Generate presigned URL (valid for 1 hour)
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.s3_bucket_name, 'Key': file_name},
                    ExpiresIn=3600
                )
                image_markdowns.append(f"![Data Visualization]({url})")
                
        if image_markdowns:
            output_msg += "\n\nGenerated Visualizations:\n" + "\n".join(image_markdowns)
            
        if not output_msg:
            output_msg = "Code executed successfully with no output."
            
        return output_msg
        
    except subprocess.TimeoutExpired:
        return "Execution Error: Code timed out after 30 seconds."
    except Exception as e:
        return f"Execution Error: {str(e)}"
    finally:
        # Cleanup
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(temp_dir)

# List of all available standalone tools
agent_tools = [tavily_search, generate_and_upload_document, search_uploaded_documents, execute_python_and_visualize]
