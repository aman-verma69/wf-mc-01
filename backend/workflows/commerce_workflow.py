"""LlamaIndex-compatible workflow boundary; deterministic services execute all financial actions."""
try:
    from llama_index.core.workflow import Workflow
except ImportError:
    Workflow = object

class CommerceWorkflow(Workflow):
    """Intent → catalog/cart/checkout → policy → payment → verification → audit."""
    pass
