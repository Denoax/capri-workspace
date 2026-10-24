"""Chosen project directory events only. Names and file contents stay unread."""
import asyncio
import ctypes
import json
import os
from pathlib import Path
import struct
from .broker import Denied
from .task_sandbox import RootHandle,validate_roots

class Projects:
    def __init__(self,store,offer,partition=None):
        self.store=store;self.offer=offer;self.partition=partition or (lambda:"local-owner");self.watching_partition=None;self.fd=None;self.watches={};self.handles=[]
        self.sources=store.value('local-owner','project-observation',[])
    def active_sources(self):return [s for s in self.sources if s.get("partition")==self.partition()]
    def choose(self,root,cloud):
        if type(cloud) is not bool:raise Denied('Invalid selected-excerpt preference')
        root=validate_roots([root])[0]
        sources=[s for s in self.sources if s['root']!=root or s.get('partition')!=self.partition()]+[{'root':root,'partition':self.partition(),'cloud':cloud,'events':'top-level saves; no file names or content'}]
        if sum(s.get('partition')==self.partition() for s in sources)>8:raise Denied('At most eight observed projects')
        self.sources=sources
        self.store.set_value('local-owner','project-observation',self.sources)
    def remove(self,root):
        self.sources=[s for s in self.sources if s['root']!=root or s.get('partition')!=self.partition()];self.store.set_value('local-owner','project-observation',self.sources)
    def start(self):
        self.stop()
        if not self.active_sources():return
        libc=ctypes.CDLL(None,use_errno=True);libc.inotify_init1.argtypes=[ctypes.c_int];libc.inotify_init1.restype=ctypes.c_int
        fd=libc.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        if fd<0:raise Denied('Local project event subscription unavailable')
        self.fd=fd;libc.inotify_add_watch.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_uint32];libc.inotify_add_watch.restype=ctypes.c_int
        try:
            self.watching_partition=self.partition()
            for source in self.active_sources():
                validate_roots([source['root']]);handle=RootHandle(source['root']);self.handles.append(handle)
                wd=libc.inotify_add_watch(fd,('/proc/self/fd/'+str(handle.fd)).encode(),0x8|0x80|0x100|0x200|0x400|0x800)
                if wd<0:raise Denied('Selected project watch unavailable')
                self.watches[wd]=source
            asyncio.get_running_loop().add_reader(fd,self.read)
        except BaseException:self.stop();raise
    def read(self):
        try:data=os.read(self.fd,65536)
        except BlockingIOError:return
        offset=0;counts={}
        while offset+16<=len(data):
            wd,mask,cookie,length=struct.unpack_from('iIII',data,offset);offset+=16+length
            if wd in self.watches:counts[wd]=counts.get(wd,0)+1
        for wd,count in counts.items():
            source=self.watches[wd]
            if source.get('partition')!=self.partition():continue
            root=source['root']
            # No filenames, source code, titles, buffers or credentials are read.
            self.offer('selected-project',root,'project-change',{'project':root,'changes':count,'cloud':source['cloud']},str(wd)+':'+str(os.times().elapsed))
    def stop(self):
        if self.fd is not None:
            asyncio.get_running_loop().remove_reader(self.fd);os.close(self.fd);self.fd=None
        for h in self.handles:h.close()
        self.handles=[];self.watches={};self.watching_partition=None
