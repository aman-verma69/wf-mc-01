from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.schemas.api_schemas import AgentChatRequest, AgentChatResponse
from backend.workflows.commerce_workflow import CommerceWorkflow

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/chat", response_model=AgentChatResponse)
async def chat(request: AgentChatRequest, db: AsyncSession = Depends(get_db)):
    workflow = CommerceWorkflow(timeout=60)
    result = await workflow.run(
        db=db,
        message=request.message,
        agent_key=request.agent_key,
        customer_id=request.customer_id,
    )
    return AgentChatResponse(**result)
