import sys
sys.path.append("../")
from reading_assistant.parsing import (
    BlockRecord,
    BookRecord,
    BookStatus,
    InMemoryParsingRepository,
    LocalBookStorage,
    NoopIndexer,
    PageRecord,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
    ParsingWorker,
    SectionRecord,
    SqlAlchemyParsingRepository,
    StoragePaths,
    WhooshIndexer,
)
from reading_assistant.parsing.engine import DoclingParsingEngine
from reading_assistant.parsing.models import BBox

import logging
from pathlib import Path



def setup_logging():
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,  # Capture everything
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),                     # Console
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),  # File
        ],
        force=True,
    )
    
setup_logging()
engine = DoclingParsingEngine()
engine.parse("../test.pdf")
print("finished")

