"""Extraction stage: turn a document into fields with confidences.

OfflineExtractor   - no services. Native PDFs: text layer + label parser.
                     Scans: reads the simulated OCR sidecar (docs/*.ocr.json).
AzureExtractor     - Azure AI Document Intelligence: prebuilt-idDocument for identity
                     documents, prebuilt-layout plus the label parser for everything else.
                     Needs AZURE_DI_ENDPOINT and AZURE_DI_KEY. pip install azure-ai-documentintelligence
"""
import json
import os
from pathlib import Path

import pdfplumber

from kit.common import doc_type_of, parse_lines


class OfflineExtractor:
    name = "offline"

    def extract(self, path):
        path = Path(path)
        if path.suffix.lower() == ".pdf":
            with pdfplumber.open(path) as pdf:
                lines = [ln for page in pdf.pages for ln in (page.extract_text() or "").splitlines()]
            return {"source": "native-text", "fields": parse_lines(lines, lambda _: 0.99)}
        sidecar = path.with_suffix(".ocr.json")
        data = json.loads(sidecar.read_text())
        return {"source": "simulated-ocr", "fields": data["fields"]}


class AzureExtractor:
    name = "azure"
    ID_FIELDS = {"LastName": "surname", "FirstName": "given_names", "DocumentNumber": "document_number",
                 "DateOfBirth": "date_of_birth", "Nationality": "nationality",
                 "DateOfExpiration": "expiry_date"}

    def __init__(self):
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        self.client = DocumentIntelligenceClient(os.environ["AZURE_DI_ENDPOINT"],
                                                 AzureKeyCredential(os.environ["AZURE_DI_KEY"]))

    def _analyze(self, model_id, path):
        with open(path, "rb") as fh:
            poller = self.client.begin_analyze_document(model_id, body=fh)
        return poller.result()

    def extract(self, path):
        if doc_type_of(path) == "identity_document":
            result = self._analyze("prebuilt-idDocument", path)
            fields = {}
            if result.documents:
                for az_name, key in self.ID_FIELDS.items():
                    f = result.documents[0].fields.get(az_name)
                    if f is not None and f.content:
                        fields[key] = {"value": f.content, "confidence": round(f.confidence or 0.0, 2)}
            return {"source": "azure:prebuilt-idDocument", "fields": fields}
        result = self._analyze("prebuilt-layout", path)
        word_conf = {}
        for page in result.pages:
            for word in page.words or []:
                word_conf[word.span.offset] = word.confidence
        line_conf = {}
        for page in result.pages:
            for line in page.lines or []:
                start = line.spans[0].offset
                end = start + line.spans[0].length
                confs = [c for off, c in word_conf.items() if start <= off < end]
                line_conf[line.content.strip()] = round(min(confs), 2) if confs else 0.0
        fields = parse_lines(list(line_conf), lambda ln: line_conf.get(ln.strip(), 0.0))
        return {"source": "azure:prebuilt-layout", "fields": fields}


def get_extractor(name):
    return AzureExtractor() if name == "azure" else OfflineExtractor()
