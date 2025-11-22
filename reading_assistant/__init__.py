"""
Reading assistant core package.

This package currently focuses on the parsing subsystem. It exposes
dataclasses for parsed content, job/state definitions, storage helpers,
a pluggable parsing engine interface, and a worker pipeline that drives
parse jobs through precheck, parse, ingestion, and indexing phases.
"""

