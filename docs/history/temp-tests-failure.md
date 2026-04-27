richardwoollcott@Mac jarvis % uv run --python 3.13 pytest
Using CPython 3.13.0 interpreter at: /usr/local/bin/python3.13
Removed virtual environment at: .venv
Creating virtual environment at: .venv
      Built jarvis @ file:///Users/richardwoollcott/Projects/appmilla_github/jarvis
Installed 125 packages in 248ms
.................................................................................F......................... [  6%]
........................................................................................................... [ 13%]
........................................................................................................... [ 20%]
........................................................................................................... [ 26%]
.................................................................F......................................... [ 33%]
........................................................................................................... [ 40%]
.........................................................................F......................F.......... [ 46%]
.......................................FF.................................................................. [ 53%]
..............................................................FFFFFFF..FFFFFFFF............................ [ 60%]
........................................................................................................... [ 66%]
........................................................................................................... [ 73%]
........................................................................................................... [ 80%]
............................................................................................ss............. [ 87%]
........................................................................................................... [ 93%]
....................................................................................................        [100%]
==================================================== FAILURES =====================================================
________________________________ TestAC001PyprojectParses.test_requires_python_312 ________________________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_build_system.py:77: in test_requires_python_312
    assert ">=3.12" in rp
E   AssertionError: assert '>=3.12' in '>=3.11'
__________ TestAC002DocstringAndAnnotation.test_docstring_matches_api_tools_md_section_1_3_byte_for_byte __________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_get_calendar_events.py:120: in test_docstring_matches_api_tools_md_section_1_3_byte_for_byte
    assert actual_docstring == contract_docstring
E   assert 'Return calen...got <value>``' == 'Return calen...got <value>``'
E
E     Skipping 39 identical leading characters in diff, use -v to show
E        window.
E
E     -     Use this tool when the user asks "what's on today", "do I have time next
E     ? ----
E     + Use this tool when the user asks "what's on today", "do I have time next...
E
E     ...Full output truncated (45 lines hidden), use '-vv' to show
_________________________ TestAC004Phase1DependenciesUntouched.test_python_pin_unchanged __________________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_phase2_dependencies.py:299: in test_python_pin_unchanged
    assert rp == ">=3.12,<3.13", (
E   AssertionError: requires-python changed from ADR-ARCH-010 pin: '>=3.11'
E   assert '>=3.11' == '>=3.12,<3.13'
E
E     - >=3.12,<3.13
E     + >=3.11
___________________ TestAC003DevExtrasIncludesLanggraphCli.test_langgraph_cli_module_importable ___________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_phase3_dependencies.py:161: in test_langgraph_cli_module_importable
    mod = importlib.import_module("langgraph_cli")
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1324: in _find_and_load_unlocked
    ???
E   ModuleNotFoundError: No module named 'langgraph_cli'
__________________________ TestAC003FakeLlm.test_fake_llm_invoke_returns_canned_response __________________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_prompts.py:317: in test_fake_llm_invoke_returns_canned_response
    result = fake_llm.invoke("Hello")
             ^^^^^^^^^^^^^^^^^^^^^^^^
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/chat_models.py:455: in invoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/chat_models.py:1198: in generate_prompt
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/chat_models.py:1000: in generate
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/_utils.py:251: in _normalize_messages
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
_______________________ TestAC003FakeLlm.test_fake_llm_second_invoke_returns_next_response ________________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_prompts.py:322: in test_fake_llm_second_invoke_returns_next_response
    first = fake_llm.invoke("First")
            ^^^^^^^^^^^^^^^^^^^^^^^^
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/chat_models.py:455: in invoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/chat_models.py:1198: in generate_prompt
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/chat_models.py:1000: in generate
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/language_models/_utils.py:251: in _normalize_messages
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
_________________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-01-calculate] __________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'f9283c4b-ef91-635b-7de1-9ebdaa5bde6a'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_________________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-02-read_file] __________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'b57e876d-1247-f857-d76d-336fc0f322c3'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
______________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-03-start_async_task] ______________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'a844f429-3b46-7f9c-bbb0-5fd3065b7fc1'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
______________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-04-start_async_task] ______________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'bd3c26c7-a32e-9f39-4ac2-9f2835e7b480'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
______________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-05-start_async_task] ______________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id '9cdd8142-dd7d-94cf-625a-123030bc7608'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
____________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-06-escalate_to_frontier] ____________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'beb42e61-f5f0-751f-22da-c5e9b529ab30'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
________________ TestRoutingScenarios.test_supervisor_routes_canned_prompt[prompt-07-queue_build] _________________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:643: in test_supervisor_routes_canned_prompt
    result: dict[str, Any] = await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'df940ac3-88dc-e90e-739c-0775dbeee924'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_____________ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-01-calculate] _____________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id '43702e76-07a1-56c9-30d5-d0fca8f3cdab'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_____________ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-02-read_file] _____________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'ef9fdba7-1fa6-8859-bd06-2e5a1cd0d82a'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_________ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-03-start_async_task] __________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'a08d84cf-9e5e-f1d4-5f5a-56dcd99557f5'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_________ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-04-start_async_task] __________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id '6629e5e8-f70d-5722-9b17-69338deb8651'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_________ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-05-start_async_task] __________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id 'fa90c6e0-bdec-29ce-e509-8333a1ef19de'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_______ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-06-escalate_to_frontier] ________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id '2b973c60-a9cd-4be6-0bb8-b9bd0baf933b'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
____________ TestZeroRealLLMCalls.test_fake_model_cursor_advances_exactly_twice[prompt-07-queue_build] ____________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:783: in test_fake_model_cursor_advances_exactly_twice
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id '121b14f6-b19c-3c07-609f-009f06f48329'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
_____________ TestProviderSDKsMockedForFrontierEscalation.test_gemini_client_invoked_via_patched_sdk ______________
/Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:834: in test_gemini_client_invoked_via_patched_sdk
    await graph.ainvoke(
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3535: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/main.py:3181: in astream
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_runner.py:304: in atick
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/pregel/_retry.py:242: in arun_with_retry
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:705: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langgraph/_internal/_runnable.py:473: in ainvoke
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:1361: in amodel_node
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/factory.py:386: in composed
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain/agents/middleware/todo.py:263: in awrap_model_call
    ???
/Users/richardwoollcott/Projects/appmilla_github/jarvis/.venv/lib/python3.13/site-packages/langchain_core/messages/base.py:216: in content_blocks
    ???
E   ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
E   During task with name 'model' and id '471118b8-95fa-e35f-a0e6-aa78db09450b'
----------------------------------------------- Captured log setup ------------------------------------------------
WARNING  jarvis.config.settings:settings.py:161 web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
------------------------------------------------ Captured log call ------------------------------------------------
INFO     jarvis.agents.supervisor:supervisor.py:244 Building supervisor graph with model=openai:jarvis-reasoner, tools=10, capabilities=4, async_subagents=1, ambient_tool_factory=supplied
INFO     jarvis.agents.supervisor:supervisor.py:333 Supervisor graph compiled successfully
================================================ warnings summary =================================================
tests/test_sessions.py:475
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_sessions.py:475: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/test_sessions.py:476
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_sessions.py:476: PytestUnknownMarkWarning: Unknown pytest.mark.integration_contract - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.integration_contract("COMPILED_SUPERVISOR_GRAPH")

tests/test_supervisor.py:358
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor.py:358: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/test_tools_queue_build.py:445
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_tools_queue_build.py:445: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/test_assemble_tool_list.py: 10 warnings
tests/test_assemble_tool_list_layer3.py: 19 warnings
tests/test_escalate_to_frontier.py: 2 warnings
tests/test_jarvis_reasoner_description.py: 14 warnings
tests/test_prompts.py: 8 warnings
tests/test_sessions.py: 1 warning
tests/test_supervisor.py: 13 warnings
tests/test_supervisor_extended_signature.py: 13 warnings
tests/test_supervisor_lifecycle_wiring.py: 8 warnings
tests/test_supervisor_no_llm_call.py: 9 warnings
tests/test_supervisor_with_tools.py: 1 warning
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/conftest.py:178: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_cli.py::TestHealthValid::test_health_valid_config_exits_zero
tests/test_cli.py::TestHealthValid::test_health_reports_supervisor_build_success
tests/test_cli.py::TestHealthValid::test_health_reports_memory_store_ready
tests/test_cli.py::TestHealthMissingKey::test_health_missing_openai_base_url_exits_one
tests/test_cli.py::TestHealthMissingKey::test_health_missing_key_names_env_var
tests/test_supervisor_no_llm_call.py::TestHealthCommandNoTokens::test_health_command_does_not_consume_tokens
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/src/jarvis/cli/main.py:115: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    config.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_openai_model_requires_openai_base_url
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:273: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_openai_model_with_base_url_passes
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:284: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_anthropic_model_requires_anthropic_api_key
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:293: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_anthropic_model_with_key_passes
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:303: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_google_genai_model_requires_google_api_key
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:312: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_google_genai_model_with_key_passes
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:322: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_error_message_names_specific_env_var
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:331: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_unknown_provider_passes_validation
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:366: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_anthropic_empty_secret_raises
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:379: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config.py::TestAC005ValidateProviderKeys::test_configuration_error_is_jarvis_error
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config.py:389: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_config_feat_j003.py::TestAC005NoRegression::test_validate_provider_keys_still_works
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_config_feat_j003.py:261: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_infrastructure.py: 5 warnings
tests/test_langgraph_json.py: 2 warnings
tests/test_lifecycle_layer2_wiring.py: 5 warnings
tests/test_lifecycle_startup_phase3.py: 12 warnings
tests/test_supervisor_lifecycle_wiring.py: 6 warnings
tests/test_supervisor_with_tools.py: 5 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/src/jarvis/infrastructure/lifecycle.py:339: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    config.validate_provider_keys()

tests/test_langgraph_json.py::TestJarvisGraphSymbolResolves::test_jarvis_graph_symbol_invocation_returns_compiled_state_graph
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_langgraph_json.py:285: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    stub_config.validate_provider_keys()

tests/test_langgraph_json.py::TestJarvisGraphSymbolResolves::test_jarvis_graph_factory_invocation_wires_layer2_hooks
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_langgraph_json.py:360: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    stub_config.validate_provider_keys()

tests/test_lifecycle_layer2_wiring.py::TestSpoofedAmbientRejected::test_attended_session_with_subagent_frame_rejects_escalation
tests/test_lifecycle_layer2_wiring.py::TestHooksPopulatedAfterStartup::test_current_session_hook_is_callable_and_returns_session_or_none
tests/test_lifecycle_layer2_wiring.py::TestHooksPopulatedAfterStartup::test_async_subagent_frame_hook_is_wired_per_assum_frontier_caller_frame
tests/test_lifecycle_layer2_wiring.py::TestIdempotentHookAssignment::test_two_consecutive_build_app_state_calls_replace_not_stack
tests/test_lifecycle_layer2_wiring.py::TestShutdownClearsHooks::test_shutdown_resets_both_hooks_to_none
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_lifecycle_layer2_wiring.py:72: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_lifecycle_startup_phase3.py: 12 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_lifecycle_startup_phase3.py:80: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_prompts.py::TestAC004TestConfigFixture::test_test_config_validate_provider_keys_succeeds
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_prompts.py:417: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    test_config.validate_provider_keys()  # Should not raise

tests/test_routing_e2e.py: 16 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_routing_e2e.py:210: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_lifecycle_wiring.py::TestAC005LifecycleWiring::test_load_stub_registry_called_with_configured_path
tests/test_supervisor_lifecycle_wiring.py::TestAC005LifecycleWiring::test_assemble_tool_list_called_with_config_and_registry
tests/test_supervisor_lifecycle_wiring.py::TestAC005LifecycleWiring::test_build_supervisor_called_with_tools_and_capabilities
tests/test_supervisor_lifecycle_wiring.py::TestAC006AppStateCapabilityRegistry::test_app_state_capability_registry_populated_from_loader
tests/test_supervisor_lifecycle_wiring.py::TestAC007StartupPerformance::test_startup_under_two_seconds
tests/test_supervisor_lifecycle_wiring.py::TestAC008Seam::test_supervisor_has_nine_tools_and_registry_has_four_entries
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_lifecycle_wiring.py:96: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_with_subagents.py: 13 warnings
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_subagents.py:118: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_compiled_supervisor_exposes_nine_tool_names
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_create_deep_agent_receives_nine_tools_alphabetically
tests/test_supervisor_with_tools.py::TestAC001NineToolWiring::test_assemble_tool_list_is_alphabetical
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_each_descriptor_block_appears_verbatim_in_system_prompt
tests/test_supervisor_with_tools.py::TestAC003CapabilityBlockInjection::test_blocks_appear_in_alphabetical_agent_id_order
tests/test_supervisor_with_tools.py::TestAC005NoLLMCallNoNetwork::test_fake_llm_response_cursor_remains_at_zero
  /Users/richardwoollcott/Projects/appmilla_github/jarvis/tests/test_supervisor_with_tools.py:113: UserWarning: web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.
    cfg.validate_provider_keys()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================================= short test summary info =============================================
FAILED tests/test_build_system.py::TestAC001PyprojectParses::test_requires_python_312 - AssertionError: assert '>=3.12' in '>=3.11'
FAILED tests/test_get_calendar_events.py::TestAC002DocstringAndAnnotation::test_docstring_matches_api_tools_md_section_1_3_byte_for_byte - assert 'Return calen...got <value>``' == 'Return calen...got <value>``'
FAILED tests/test_phase2_dependencies.py::TestAC004Phase1DependenciesUntouched::test_python_pin_unchanged - AssertionError: requires-python changed from ADR-ARCH-010 pin: '>=3.11'
FAILED tests/test_phase3_dependencies.py::TestAC003DevExtrasIncludesLanggraphCli::test_langgraph_cli_module_importable - ModuleNotFoundError: No module named 'langgraph_cli'
FAILED tests/test_prompts.py::TestAC003FakeLlm::test_fake_llm_invoke_returns_canned_response - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_prompts.py::TestAC003FakeLlm::test_fake_llm_second_invoke_returns_next_response - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-01-calculate] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-02-read_file] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-03-start_async_task] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-04-start_async_task] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-05-start_async_task] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-06-escalate_to_frontier] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestRoutingScenarios::test_supervisor_routes_canned_prompt[prompt-07-queue_build] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-01-calculate] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-02-read_file] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-03-start_async_task] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-04-start_async_task] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-05-start_async_task] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-06-escalate_to_frontier] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestZeroRealLLMCalls::test_fake_model_cursor_advances_exactly_twice[prompt-07-queue_build] - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
FAILED tests/test_routing_e2e.py::TestProviderSDKsMockedForFrontierEscalation::test_gemini_client_invoked_via_patched_sdk - ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'
21 failed, 1575 passed, 2 skipped, 215 warnings in 13.34s
richardwoollcott@Mac jarvis %