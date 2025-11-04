from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.sql_database import SQLDatabase
from langchain_community.chat_models import BedrockChat
import boto3
import os

def get_agent_and_db():
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
    db_uri = os.getenv("DB_URI", "postgresql://user:password@db:5432/postgres")

    
    llm = BedrockChat(
        client=bedrock_runtime,
        model_id=model_id,
        model_kwargs={"temperature": 0}
    )

    db = SQLDatabase.from_uri(db_uri)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,
        handle_parsing_errors=True,
        agent_executor_kwargs = {"return_intermediate_steps": True})


    return agent_executor, db
