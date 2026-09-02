from app.agent.memory import Memory


def test_graph_node_created_on_remember(tmp_db):
    memory = Memory()
    # remember an object with room and area
    memory.remember_object_location('livro', 'prateleira norte', room='sala', area='prateleira norte', confidence=0.9)

    # check graph_nodes has an object node
    conn = memory._db_path
    from app.db import get_connection
    c = get_connection(memory._db_path)
    rows = c.execute("SELECT * FROM graph_nodes WHERE label = ?", ('livro',)).fetchall()
    assert len(rows) == 1
    node = rows[0]
    assert node['type'] == 'object'
    assert node['object_name'] == 'livro'

    # ensure a room node exists
    rooms = c.execute("SELECT * FROM rooms WHERE name = ?", ('sala',)).fetchall()
    assert len(rooms) == 1

    # ensure there's an edge from room/area node to object (relation contains)
    edges = c.execute("SELECT * FROM graph_edges").fetchall()
    assert len(edges) >= 1
