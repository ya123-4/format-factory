"""Document conversion tests (Task 11) — matrix and argument building."""
import threading
import time

from app.engine.document import DocConverter, build_soffice_args, doc_supported


def test_doc_matrix_supported():
    assert doc_supported("docx", "pdf") is True
    assert doc_supported("odt", "docx") is True
    assert doc_supported("xlsx", "txt") is True
    assert doc_supported("pptx", "txt") is True
    assert doc_supported("txt", "xlsx") is False
    assert doc_supported("pdf", "docx") is False
    assert doc_supported("docx", "xlsx") is False


def _convert_to(args):
    return args[args.index("--convert-to") + 1]


def test_matrix_xlsx_txt_uses_csv():
    args = build_soffice_args("a.xlsx", "out", "txt", "C:/prof")
    conv = _convert_to(args)
    assert "txt" in conv and "csv" in conv


def test_matrix_pptx_txt_uses_outline():
    args = build_soffice_args("a.pptx", "out", "txt", "C:/prof")
    conv = _convert_to(args)
    assert "txt" in conv and "impress" in conv


def test_soffice_args_contain_user_installation():
    args = build_soffice_args("a.docx", "out", "pdf", "C:/prof")
    assert "--headless" in args
    assert "--outdir" in args and args[args.index("--outdir") + 1] == "out"
    env = next(a for a in args if a.startswith("-env:UserInstallation="))
    assert env == "-env:UserInstallation=file:///C:/prof"
    assert args[-1] == "a.docx"


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
