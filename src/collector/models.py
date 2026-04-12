from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ProcessInfo(BaseModel):
    exec_id: str
    pid: int
    uid: int
    cwd: str
    binary: str
    arguments: str
    flags: str
    start_time: datetime
    auid: int
    pod: Optional[Dict[str, Any]] = None

class SyscallEvent(BaseModel):
    process: ProcessInfo
    parent: Optional[ProcessInfo] = None
    syscall: str
    args: List[Any]
    return_value: Optional[int] = None
    time: datetime

class TetragonEvent(BaseModel):
    process_kprobe: Optional[SyscallEvent] = None
    process_exec: Optional[ProcessInfo] = None
    process_exit: Optional[ProcessInfo] = None
    node_name: str
    time: datetime

class CiliumFlowEvent(BaseModel):
    source: Dict[str, Any]
    destination: Dict[str, Any]
    IP: Optional[Dict[str, Any]] = None
    L4: Optional[Dict[str, Any]] = None
    type: str # L3/L4/L7
    node_name: str
    time: datetime

class FalcoEvent(BaseModel):
    output: str
    priority: str
    rule: str
    time: datetime
    output_fields: Dict[str, Any]

class CombinedEvent(BaseModel):
    tetragon: Optional[TetragonEvent] = None
    cilium: Optional[CiliumFlowEvent] = None
    falco: Optional[FalcoEvent] = None

