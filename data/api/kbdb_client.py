"""KBDB API (HRDB-API) 共通クライアント。

Usage:
    from kbdb_client import KBDBClient
    client = KBDBClient()
    rows = client.query("SELECT * FROM HORSE WHERE BLDNO='2002101448';")
"""
import csv
import io
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE_URL = "https://api.gamble-os.net/systems/hrdb"
POLL_INTERVAL = 2
MAX_POLLS = 30


class KBDBClient:
    def __init__(self):
        self.tncid = os.environ["TNCID"]
        self.tncpw = os.environ["TNCPW"]

    def _auth(self) -> dict:
        return {"tncid": self.tncid, "tncpw": self.tncpw}

    def query(self, sql: str) -> list[dict]:
        """SQLを実行し、結果をdictのリストで返す。"""
        qid = self._submit(sql)
        self._wait(qid)
        return self._fetch_csv(qid)

    def _submit(self, sql: str) -> str:
        resp = requests.post(BASE_URL, data={
            **self._auth(),
            "prccd": "select",
            "cmd1": sql,
            "format": "json",
        })
        data = resp.json()
        if data.get("ret") != 0:
            raise RuntimeError(f"KBDB submit error: {data}")
        return data["ret1"]

    def _wait(self, qid: str) -> None:
        for _ in range(MAX_POLLS):
            time.sleep(POLL_INTERVAL)
            resp = requests.post(BASE_URL, data={
                **self._auth(),
                "prccd": "state",
                "qid1": qid,
            })
            state = resp.json()
            ret1 = str(state.get("ret1"))
            if ret1 == "2":
                return
            if ret1 == "6":
                raise RuntimeError(f"KBDB SQL error (state=6) for qid={qid}")
            if ret1 == "4":
                raise RuntimeError(f"KBDB execution failed (state=4) for qid={qid}")
        raise TimeoutError(f"KBDB query timed out for qid={qid}")

    def _fetch_csv(self, qid: str) -> list[dict]:
        resp = requests.post(BASE_URL, data={
            **self._auth(),
            "prccd": "getcsv",
            "qid1": qid,
        })
        text = resp.content.decode("cp932")
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
