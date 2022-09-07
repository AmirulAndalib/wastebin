import os
import time
from threading import Thread
from typing import Optional

from deta import Deta

from document import Document


class DocumentDB:
    def get(self, id: str) -> Optional[Document]:
        raise NotImplementedError

    def put(self, document: Document) -> str:
        raise NotImplementedError


class FileDB(DocumentDB):
    def __init__(self, path: str = './data/documents', clean_interval: int = 60 * 60 * 24):
        self.path = path
        self._clean_interval = clean_interval
        if not os.path.exists(self.path):
            os.makedirs(self.path, exist_ok=True)
        self._clean_thread = Thread(target=self._clean_expired, daemon=True)
        self._clean_thread.start()

    def _clean_expired(self):
        while True:
            for name in os.listdir(self.path):
                path = os.path.join(self.path, name)
                if os.path.isfile(path):
                    document = Document.parse_file(path)
                    if document.expire_at and document.expire_at < int(time.time()):
                        os.remove(path)
            time.sleep(self._clean_interval)

    def get(self, id: str) -> Optional[Document]:
        try:
            return Document.parse_file(f'{self.path}/{id}.json')
        except OSError:
            return None

    def put(self, document: Document) -> str:
        path = f'{self.path}/{document.id}.json'
        if os.path.exists(path):
            raise ValueError("file already exists")
        with open(path, 'w') as file:
            file.write(document.json())
        return document.id


class DetaDB(DocumentDB):
    def __init__(self, name: str, deta_key: Optional[str] = None):
        deta_key = deta_key or os.getenv('DETA_PROJECT_KEY')
        if not deta_key:
            raise ValueError('no Deta project key provided')
        self._deta = Deta(deta_key)
        self._db = self._deta.Base(name)

    def get(self, id: str) -> Optional[Document]:
        document = self._db.get(id)
        if document:
            return Document.parse_obj(document)

    def put(self, document: Document) -> str:
        document.highlight()
        self._db.insert(document.dict(), key=document.id, expire_at=document.expire_at)
        return document.id