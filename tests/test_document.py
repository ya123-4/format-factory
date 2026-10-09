"""Document conversion tests (Task 11, rev 3) — LibreOffice Kit matrix."""
import threading
import time

from app.engine.document import DocConverter, build_kit_args, doc_supported


def test_doc_matrix_supported():
    assert doc_supported("docx", "pdf") is True
    assert doc_supported("odt", "docx") is True
    assert doc_supported("docx", "txt") is True
    assert doc_supported("xlsx", "csv") is True
    assert doc_supported("xlsx", "pdf") is True
    assert doc_supported("pptx", "pdf") is True
    # 矩阵外（Kit 实测不支持）
    assert doc_supported("txt", "pdf") is False
    assert doc_supported("pdf", "txt") is False
    assert doc_supported("docx", "xlsx") is False
    assert doc_supported("pptx", "txt") is False
    assert doc_supported("xlsx", "txt") is False
    assert doc_supported("docx", "csv") is False


def test_build_kit_args():
    args = build_kit_args("node.exe", "cli.js", "a.docx", "out.pdf")
    assert args == ["node.exe", "cli.js", "convert", "--input", "a.docx", "--output", "out.pdf"]


def test_single_instance_lock():
    lock = DocConverter._lock
    assert isinstance(lock, type(threading.Lock()))
    results = []

    def holder():
        with lock:
            results.append("held")
            time.sleep(0.4)

    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.1)
    assert results == ["held"]
    assert lock.acquire(timeout=0.2) is False  # 同一把类级锁，被持有（失败不占锁）
    t.join()
