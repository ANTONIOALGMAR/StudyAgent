from app.agent.memory import Memory


def test_reconcile_creates_entry(tmp_db):
    memory = Memory()
    # no existing entry
    bbox = {"left": 10, "top": 20, "width": 100, "height": 80}
    memory.reconcile_detection('celular', bbox, monitor=0, context='detected on camera', confidence=0.9)

    rec = memory.find_object_location('celular')
    assert rec is not None
    assert 'monitor 0' in rec['location']
    assert rec['confidence'] >= 0.9 - 1e-6


def test_reconcile_overwrites_with_higher_confidence(tmp_db):
    memory = Memory()
    # create existing low-confidence record
    memory.remember_object_location('celular', 'mesa antiga', room='quarto', context='entrada manual', confidence=0.5)

    bbox = {"left": 1, "top": 2, "width": 10, "height": 10}
    # detection has higher confidence (0.8 >= 0.5 + 0.15)
    memory.reconcile_detection('celular', bbox, monitor=1, context='detected structured', confidence=0.8)

    rec = memory.find_object_location('celular')
    assert rec is not None
    assert 'monitor 1' in rec['location']
    # confidence should be updated to at least 0.8
    assert rec['confidence'] >= 0.8 - 1e-6


def test_reconcile_detects_contradiction_and_notifies(tmp_db):
    memory = Memory()
    # create existing high-confidence record
    memory.remember_object_location('chave', 'prateleira antiga', room='entrada', context='manual', confidence=0.95)

    bbox = {"left": 5, "top": 5, "width": 20, "height": 20}
    # detection with lower confidence triggers contradiction (0.7 <= 0.95 - 0.15)
    memory.reconcile_detection('chave', bbox, monitor=0, context='detected elsewhere', confidence=0.7)

    rec = memory.find_object_location('chave')
    assert rec is not None
    # existing confidence should be slightly reduced from 0.95 -> ~0.855
    assert rec['confidence'] < 0.95
    assert rec['confidence'] >= 0.855 - 1e-6

    # inbox_entries should contain a notification
    conn = memory._db_path
    # use get_connection to query inbox_entries
    from app.db import get_connection
    c = get_connection(memory._db_path)
    rows = c.execute("SELECT * FROM inbox_entries").fetchall()
    assert len(rows) >= 1
    found = any('Contradição' in (r['title'] or '') or 'contradição' in (r['title'] or '').lower() for r in rows)
    assert found
