from unittest.mock import patch


class TestEnvironmentMemory:
    def test_remember_and_find_object_location(self, tmp_db):
        from app.agent.memory import Memory

        memory = Memory()
        memory.remember_object_location('celular', 'mesa da direita', room='quarto', context='o celular está na mesa da direita no quarto')

        result = memory.find_object_location('celular')
        assert result is not None
        assert 'mesa da direita' in result['location']
        assert result['room'] == 'quarto'

        related = memory.find_related_objects('onde está o celular', limit=5)
        assert related and any(item['object_name'] == 'celular' for item in related)

    def test_agent_can_resolve_known_object_location(self, tmp_db):
        from app.agent.agent import StudyAgent

        agent = StudyAgent()
        agent.memory.remember_object_location('celular', 'mesa da direita', room='quarto', context='o celular está na mesa da direita no quarto')

        agent._remember_object_from_message('deixei o celular em cima da mesa da direita no quarto')
        answer = agent._resolve_object_location('onde está o celular?')

        assert answer is not None
        assert 'mesa da direita' in answer.lower()
        assert 'quarto' in answer.lower()

    def test_agent_extracts_object_name_for_visual_lookups(self, tmp_db):
        from app.agent.agent import StudyAgent

        agent = StudyAgent()
        assert agent._extract_object_name('onde está o celular?') == 'celular'
        assert agent._extract_object_name('procure a chave no ambiente') == 'chave'

    def test_room_hint_is_used_in_lookup(self, tmp_db):
        from app.agent.memory import Memory

        memory = Memory()
        memory.remember_object_location('chave', 'prateleira da parede', room='entrada', context='chave na entrada')
        memory.remember_object_location('chave', 'mesa de canto', room='quarto', context='chave no quarto')

        result = memory.find_object_location('chave', room='quarto')
        assert result is not None
        assert result['room'] == 'quarto'
        assert 'mesa de canto' in result['location']

    @patch('app.agent.agent.chat')
    def test_agent_uses_visual_context_for_object_location_requests(self, mock_chat, tmp_db):
        from app.agent.agent import StudyAgent

        mock_chat.return_value = 'O celular está em cima da mesa da direita.'
        agent = StudyAgent()
        agent.memory.remember_object_location('celular', 'mesa da direita', room='quarto', context='o celular está na mesa da direita no quarto')

        agent.process('onde está o celular?', camera_image=b'fake-bytes')

        messages = mock_chat.call_args[0][0]
        joined = '\n'.join(message['content'] for message in messages if isinstance(message, dict) and 'content' in message)
        assert '[LOCALIZAÇÃO DE OBJETO]' in joined
        assert 'mesa da direita' in joined or 'memória do ambiente' in joined

    def test_build_plan_auto_enables_visual_capture_for_environment_queries(self, tmp_db):
        from app.core.planner import build_plan

        planned = build_plan('onde está o celular?', use_screen_requested=False)
        assert planned.capture_screen is True
        assert planned.vision_required is True

    def test_room_semantics_are_exposed_for_visual_mapping(self, tmp_db):
        from app.agent.memory import Memory

        memory = Memory()
        memory.remember_object_location('celular', 'mesa da direita', room='quarto', area='mesa da direita', context='o celular está na mesa da direita do quarto')

        room_items = memory.find_objects_in_room(room='quarto', limit=10)
        assert room_items and any(item['object_name'] == 'celular' for item in room_items)

    def test_agent_natural_response_mentions_area_and_room(self, tmp_db):
        from app.agent.agent import StudyAgent

        agent = StudyAgent()
        agent.memory.remember_object_location('celular', 'mesa da direita', room='quarto', area='mesa da direita', context='o celular está na mesa da direita do quarto')

        result = agent._resolve_object_location('onde está o celular no quarto?')
        assert 'quarto' in result.lower()
        assert 'mesa da direita' in result.lower()

    def test_agent_lists_room_inventory_naturally(self, tmp_db):
        from app.agent.agent import StudyAgent

        agent = StudyAgent()
        agent.memory.remember_object_location('celular', 'mesa da direita', room='quarto', area='mesa da direita', context='celular no quarto')
        agent.memory.remember_object_location('chave', 'prateleira', room='quarto', area='prateleira', context='chave no quarto')

        result = agent._resolve_room_inventory('o que tem no quarto?')
        assert result is not None
        assert 'celular' in result.lower()
        assert 'chave' in result.lower()

    def test_agent_keeps_area_metadata_for_natural_locations(self, tmp_db):
        from app.agent.agent import StudyAgent

        agent = StudyAgent()
        agent._remember_object_from_message('deixei o celular na mesa da direita do quarto')

        record = agent.memory.find_object_location('celular', room='quarto')
        assert record is not None
        assert record['room'] == 'quarto'
        assert 'mesa da direita' in (record['area'] or record['location'])

    @patch('app.agent.agent.ScreenManager')
    def test_object_lookup_falls_back_to_memory_when_visual_capture_fails(self, mock_sm, tmp_db):
        from app.agent.agent import StudyAgent

        mock_sm.list_monitors.return_value = [{'index': 0, 'name': 'monitor-0'}]
        mock_sm.capture_monitor.side_effect = RuntimeError('capture failed')

        agent = StudyAgent()
        agent.memory.remember_object_location('celular', 'mesa da direita', room='quarto', context='o celular está na mesa da direita no quarto')

        result = agent.process('onde está o celular?', use_screen=True)
        assert 'mesa da direita' in result['response'].lower()
        assert 'quarto' in result['response'].lower()
