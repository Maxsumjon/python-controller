import threading
import socket
import json
from enum import Enum
import time
import logging


class DataType(str, Enum):
    BOOL = 'bool'
    BYTE = 'byte'
    WORD = 'word'
    DWORD = 'dword'
    QWORD = 'qword'
    INT = 'int'
    FLOAT = 'float'
    STRING = 'str'
    
class UDP_Controller(threading.Thread):

    def __init__(self, ip:str="0.0.0.0", port:int=8400, max_size:int=1024, log_lever=logging.ERROR):
        logging.basicConfig(level=log_lever, format='%(asctime)-15s %(levelname)s %(name)s: %(message)s')
        self._ip = ip
        self._port = port
        self._max_size = max_size
        self._client_address = None
        self._running = True
        self._variables = {}
        self._pending2send = {}
        threading.Thread.__init__(self, name="Simumatik Controller", daemon=True)

    def close(self):
        self._running = False

    def addVariable(self, name:str, datatype:DataType, value:any):
        assert name not in self._variables, f"Variable {name} already defined!"
        value = self.checkValue(value, datatype)
        self._variables.update({name: {"datatype":datatype, "value":value}})

    def setValue(self, name:str, new_value:any, send_update=True):
        assert name in self._variables, f"Variable {name} is not defined!"
        new_value = self.checkValue(new_value, self._variables[name]["datatype"])
        if new_value != self._variables[name]["value"]:
            self._variables[name]["value"] = new_value
            if send_update:
                self._pending2send.update({name:new_value})

    def getValue(self, name:str):
        assert name in self._variables, f"Variable {name} is not defined!"
        return self._variables[name]["value"]

    def checkValue(self, value:any, datatype:DataType):
        if datatype == DataType.BOOL:
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value == 'True'
            else:
                return False
        elif datatype in [DataType.BYTE, DataType.WORD, DataType.DWORD, DataType.QWORD, DataType.INT]:
            return int(value)
        elif datatype == DataType.FLOAT:
            return float(value)
        else:
            return str(value)

    def run(self):
        _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _socket.bind((self._ip, self._port))
        _socket.settimeout(0)
        logging.debug(f"Controller UDP server listening: {self._ip}: {self._port}")
        
        while self._running:

            _recv_data = {}
            _send_data = {}
            _addr = None

            try:
                _data, _addr = _socket.recvfrom(self._max_size) # buffer size is 4096 bytes
                if _addr != self._client_address:
                    self._client_address = _addr
                    logging.info(f"New connection stablished: {self._client_address}")
                    
                _recv_data = json.loads(_data.decode('utf-8'))
                logging.debug(f"Data received: {_recv_data}")
                    
            except:
                pass
                
            if self._client_address is not None:

                if _recv_data:
                    if _recv_data.get("poll", None):
                        _recv_data.pop("poll")
                        _send_data.update({"poll":int(time.perf_counter())})
                        
                    for var_name, var_value in _recv_data.items():
                        self.setValue(var_name, var_value, send_update=False)

                while self._pending2send:
                    (var_name, var_value) = self._pending2send.popitem()
                    _send_data.update({var_name:var_value})

                if _send_data:
                    _socket.sendto(json.dumps(_send_data).encode('utf-8'), self._client_address)
                    logging.debug(f"Data sent: {_send_data}")

            time.sleep(1e-6)

        _socket.close()
        _socket = None