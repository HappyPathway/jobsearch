from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DocumentBase(BaseModel):
    title: str
    doc_type: str  # "resume" or "cover_letter"
    job_id: Optional[int] = None
    template_name: Optional[str] = "default"

class DocumentCreate(DocumentBase):
    content: Optional[str] = None
    use_visual_resume: Optional[bool] = True
    include_projects: Optional[bool] = True
    
class DocumentResponse(DocumentBase):
    id: int
    created_at: datetime
    modified_at: datetime
    gcs_path: str
    download_url: Optional[str] = None
    
    class Config:
        from_attributes = True
        
class GenerationOptions(BaseModel):
    template_name: Optional[str] = "default"
    use_visual_resume: Optional[bool] = True
    include_projects: Optional[bool] = True
    writing_enhancement: Optional[bool] = True
    
class GenerateRequest(BaseModel):
    job_id: int
    options: Optional[GenerationOptions] = GenerationOptions()
    
class GenerateResponse(BaseModel):
    resume_id: int
    cover_letter_id: int
    resume_url: str
    cover_letter_url: str
    generation_time: datetime
    status: str = "completed"