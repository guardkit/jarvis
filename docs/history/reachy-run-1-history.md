(reachy-mini-conversation-app) richardwoollcott@Richards-MBP reachy_mini_conversation_app % python -c "from reachy_mini_conversation_app.main import main; main()"
Environment variable 'REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY' is set. Profiles (instructions.txt, ...) will be loaded from /Users/richardwoollcott/Projects/appmilla_github/fleet-gateway/reachy/external_content/external_profiles.
Environment variable 'REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY' is set. External tools will be loaded from /Users/richardwoollcott/Projects/appmilla_github/fleet-gateway/reachy/external_content/external_tools.
2026-05-13 19:18:54,905 INFO reachy_mini_conversation_app.utils:66 | Starting Reachy Mini Conversation App
2026-05-13 19:18:54,906 INFO reachy_mini_conversation_app.utils:87 | Configured backend provider: huggingface (Hugging Face), connection mode: deployed
2026-05-13 19:18:55,480 INFO reachy_mini_conversation_app.tools.core_tools:144 | Loading tools for profile: scholar
2026-05-13 19:18:55,480 INFO reachy_mini_conversation_app.tools.core_tools:153 | Loading external profile 'scholar' from /Users/richardwoollcott/Projects/appmilla_github/fleet-gateway/reachy/external_content/external_profiles/scholar
2026-05-13 19:18:55,481 INFO reachy_mini_conversation_app.tools.core_tools:192 | Found 9 tools to load: ['ask_jarvis', 'query_student_model', 'celebrate_achievement', 'camera', 'emotion', 'dance', 'head_tracking', 'task_status', 'task_cancel']
2026-05-13 19:18:55,663 INFO reachy_mini_conversation_app.tools.core_tools:245 | ✓ Loaded external tool: ask_jarvis
2026-05-13 19:18:55,663 INFO reachy_mini_conversation_app.tools.core_tools:245 | ✓ Loaded external tool: query_student_model
2026-05-13 19:18:55,664 INFO reachy_mini_conversation_app.tools.core_tools:245 | ✓ Loaded external tool: celebrate_achievement
2026-05-13 19:18:55,664 INFO reachy_mini_conversation_app.tools.core_tools:247 | ✓ Loaded core tool: camera
2026-05-13 19:18:55,664 WARNING reachy_mini_conversation_app.tools.core_tools:252 | ⚠️ Tool 'emotion' not found in profile or shared tools
2026-05-13 19:18:55,668 INFO reachy_mini_conversation_app.tools.core_tools:247 | ✓ Loaded core tool: dance
2026-05-13 19:18:55,668 INFO reachy_mini_conversation_app.tools.core_tools:247 | ✓ Loaded core tool: head_tracking
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:247 | ✓ Loaded core tool: task_status
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:247 | ✓ Loaded core tool: task_cancel
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:272 | tool registered: ask_jarvis - Send a question to Jarvis, the Ship's Computer. Jarvis routes it to the right specialist agent — study tutor for revision help, architect for technical decisions, forge for build status. Use this for any question that needs an expert answer. Returns text you can speak directly.
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:272 | tool registered: camera - Take a picture with the camera and ask a question about it.
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:272 | tool registered: dance - Play a named or random dance move once (or repeat). Non-blocking.
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:272 | tool registered: head_tracking - Toggle head tracking state.
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:272 | tool registered: task_status - Check the status of background tool tasks. Use this when the user asks about running tools or wants to know what's happening in the background.
2026-05-13 19:18:55,669 INFO reachy_mini_conversation_app.tools.core_tools:272 | tool registered: task_cancel - Cancel a running background tool task. Use this when the user wants to stop a tool that's running in the background. Requires confirmation before cancelling.
2026-05-13 19:18:55,670 INFO reachy_mini_conversation_app.utils:114 | Initializing ReachyMini (SDK will auto-detect appropriate backend)
2026-05-13 19:18:55,710 INFO reachy_mini.reachy_mini:432 | Connection mode selected: localhost_only
/Users/richardwoollcott/Projects/appmilla_github/reachy_mini_conversation_app/.venv/lib/python3.10/site-packages/reachy_mini/reachy_mini.py:164: RuntimeWarning: Reachy Mini SDK and daemon versions do not match: SDK=1.7.1, daemon=1.7.3. Running different versions can create issues. Install matching reachy_mini versions for the SDK and daemon.
  self.media_manager = self._configure_mediamanager(media_backend, log_level)
2026-05-13 19:18:56,595 INFO reachy_mini.reachy_mini:313 | No local IPC endpoint. Using WebRTC backend for streaming.
2026-05-13 19:18:56,595 INFO reachy_mini.media.media_manager:167 | Using WebRTC streaming backend.
2026-05-13 19:18:56,846 ERROR reachy_mini.media.audio_control_utils:550 | No Reachy Mini Audio USB device found!
2026-05-13 19:18:56,956 INFO reachy_mini.media.webrtc_client_gstreamer:150 | GstWebRTCClient initialized (bidirectional audio support)
2026-05-13 19:18:57,066 INFO reachy_mini.media.webrtc_client_gstreamer:191 | Captured webrtcbin: webrtcbin0
2026-05-13 19:18:57,068 INFO reachy_mini.media.webrtc_client_gstreamer:220 | Transceiver configured for SENDRECV
2026-05-13 19:18:57,161 INFO reachy_mini.media.webrtc_client_gstreamer:220 | Transceiver configured for SENDRECV
2026-05-13 19:18:57,620 INFO reachy_mini_conversation_app.utils:111 | Using the selected realtime backend for vision (default). Use --local-vision for local processing.
2026-05-13 19:18:57,654 INFO reachy_mini.media.webrtc_client_gstreamer:373 | Setting up audio send chain...
2026-05-13 19:18:57,655 INFO reachy_mini.media.webrtc_client_gstreamer:394 | Found audio sink pad: sink_1, pt=100
2026-05-13 19:18:57,675 INFO reachy_mini.media.webrtc_client_gstreamer:448 | Audio send chain ready (bidirectional audio enabled)
2026-05-13 19:18:58,210 INFO reachy_mini_conversation_app.utils:201 | Using Hugging Face via Hugging Face realtime handler (Hugging Face session proxy)
2026-05-13 19:18:59,213 ERROR reachy_mini.media.audio_control_utils:550 | No Reachy Mini Audio USB device found!
2026-05-13 19:18:59,213 WARNING reachy_mini.media.webrtc_client_gstreamer:137 | ReSpeaker device not found.
2026-05-13 19:18:59,213 WARNING reachy_mini_conversation_app.console:58 | Reachy audio startup config was not applied.
2026-05-13 19:19:00,132 INFO httpx:1740 | HTTP Request: POST https://pollen-robotics-reachy-mini-realtime-url.hf.space/session "HTTP/1.1 200 OK"
2026-05-13 19:19:00,170 INFO reachy_mini_conversation_app.huggingface_realtime:154 | Allocated realtime session Qv-Das-5JwEpbplLhqS5hnJF
2026-05-13 19:19:00,176 INFO reachy_mini_conversation_app.base_realtime:656 | Tools to be used in conversation: ['ask_jarvis', 'camera', 'dance', 'task_status', 'task_cancel']
2026-05-13 19:19:01,067 INFO reachy_mini_conversation_app.prompts:69 | Loading prompt from external profile 'scholar' (root=/Users/richardwoollcott/Projects/appmilla_github/fleet-gateway/reachy/external_content/external_profiles)
2026-05-13 19:19:01,069 WARNING reachy_mini_conversation_app.base_realtime:201 | Ignoring unsupported session voice 'Kore' for backend='huggingface'; expected one of ['Aiden', 'Ryan', 'Dylan', 'Eric', 'Ono_Anna', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian']
2026-05-13 19:19:01,071 WARNING reachy_mini_conversation_app.base_realtime:201 | Ignoring unsupported session voice 'Kore' for backend='huggingface'; expected one of ['Aiden', 'Ryan', 'Dylan', 'Eric', 'Ono_Anna', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian']
2026-05-13 19:19:01,071 INFO reachy_mini_conversation_app.base_realtime:669 | Realtime session initialized with profile='scholar' voice='Aiden'
2026-05-13 19:19:01,071 INFO reachy_mini_conversation_app.base_realtime:679 | Realtime session updated successfully
2026-05-13 19:19:01,071 INFO reachy_mini_conversation_app.tools.background_tool_manager:320 | BackgroundToolManager started. Max tool execution duration: 86400 seconds (tools running longer will be auto-cancelled). Max tool memory retention: 3600 seconds (completed/failed/cancelled tools older than this are purged).
2026-05-13 19:20:26,953 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:20:27,883 INFO reachy_mini_conversation_app.console:674 | role=user content=Hey Richie, you right?
2026-05-13 19:20:29,178 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Yeah, I'm good, thanks — nice to hear you. You alright?
2026-05-13 19:20:29,495 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 1690 ms after user transcript
2026-05-13 19:20:34,937 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:20:39,462 INFO reachy_mini_conversation_app.console:674 | role=user content=Yeah, I'm good. Could you ask Jarvis what tools are available, please? What agents?
2026-05-13 19:20:40,863 INFO reachy_mini_conversation_app.base_realtime:833 | Tool call received — tool_name='ask_jarvis', call_id=call_e8d6f87dd9194b0aae0032ff09d44671, is_idle=False, args={"message":"What tools and specialist agents are currently available to me through Jarvis? Please give a concise overview I can relay aloud."}
2026-05-13 19:20:40,865 INFO reachy_mini_conversation_app.tools.background_tool_manager:200 | Started background tool: ask_jarvis (id=call_e8d6f87dd9194b0aae0032ff09d44671)
2026-05-13 19:20:40,865 INFO reachy_mini_conversation_app.base_realtime:870 | Started background tool: ask_jarvis (id=ask_jarvis-call_e8d6f87dd9194b0aae0032ff09d44671-1365535.363272625, call_id=call_e8d6f87dd9194b0aae0032ff09d44671)
2026-05-13 19:20:40,900 INFO reachy_mini_conversation_app.console:674 | role=assistant content=🛠️ Used tool ask_jarvis with args {"message":"What tools and specialist agents are currently available to me through Jarvis? Please give a concise overview I can relay aloud."}. The tool is now running. Tool ID: ask_jarvis-call_e8d6f87dd9194b0aae0032ff09d44671-1365535.363272625
2026-05-13 19:20:47,970 INFO ask_jarvis:134 | AskJarvisTool: Jarvis responded (980 chars) for adapter=reachy-scholar
2026-05-13 19:20:47,980 INFO reachy_mini_conversation_app.base_realtime:541 | Tool 'ask_jarvis' (id=call_e8d6f87dd9194b0aae0032ff09d44671) executed successfully.
2026-05-13 19:20:48,003 INFO reachy_mini_conversation_app.console:674 | role=assistant content={"response": "Here's a concise overview you can relay:\n\n**Specialist agents available:**\n- **Architect** \u2014 for architecture sessions, C4 diagrams, and ADRs\n- **Product Owner** \u2014 for spec reviews, prioritisation, and acceptance criteria\n- **GCSE Tutor** \u2014 for interactive tutoring across English Lit, English Language, Maths, Sciences, History, and more\n- **Ideation** \u2014 for generating alternatives and counter-arguments\n- **Forge** \u2014 for building features from YAML sp…
2026-05-13 19:20:48,234 INFO reachy_mini_conversation_app.base_realtime:730 | Turn latency: response.created 8793 ms after user transcript
2026-05-13 19:20:50,237 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Yep — Jarvis says the specialist agents are Architect, Product Owner, GCSE Tutor, Ideation, Forge, and Frontier Escalation for cloud models. The main tools include calculate, web search, calendar, file tools, and task tools for subagents and async work.
2026-05-13 19:20:50,522 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 11081 ms after user transcript
2026-05-13 19:21:15,313 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:21:15,823 INFO reachy_mini_conversation_app.console:674 | role=user content=Sounds cool.
2026-05-13 19:21:17,541 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Yeah, it's a handy little crew. If you want, I can ask Jarvis to use one of them for something now.
2026-05-13 19:21:17,810 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 2046 ms after user transcript
2026-05-13 19:21:27,686 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:21:31,791 INFO reachy_mini_conversation_app.console:674 | role=user content=Yeah, sure. Could you ask um Jarvis to do a search, a web search?
2026-05-13 19:21:32,986 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Yep — what do you want me to search for?
2026-05-13 19:21:33,216 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 1480 ms after user transcript
2026-05-13 19:21:34,615 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:21:35,388 INFO reachy_mini_conversation_app.console:674 | role=user content=Talk factory.
2026-05-13 19:21:37,017 INFO reachy_mini_conversation_app.base_realtime:833 | Tool call received — tool_name='ask_jarvis', call_id=call_f9f1a47428e941acb47a74eae8a06a7d, is_idle=False, args={"message":"Please do a web search for 'Talk Factory' and give me a brief spoken summary of what it is, plus the most likely official website if clear."}
2026-05-13 19:21:37,018 INFO reachy_mini_conversation_app.tools.background_tool_manager:200 | Started background tool: ask_jarvis (id=call_f9f1a47428e941acb47a74eae8a06a7d)
2026-05-13 19:21:37,018 INFO reachy_mini_conversation_app.base_realtime:870 | Started background tool: ask_jarvis (id=ask_jarvis-call_f9f1a47428e941acb47a74eae8a06a7d-1365591.515460458, call_id=call_f9f1a47428e941acb47a74eae8a06a7d)
2026-05-13 19:21:37,075 INFO reachy_mini_conversation_app.console:674 | role=assistant content=🛠️ Used tool ask_jarvis with args {"message":"Please do a web search for 'Talk Factory' and give me a brief spoken summary of what it is, plus the most likely official website if clear."}. The tool is now running. Tool ID: ask_jarvis-call_f9f1a47428e941acb47a74eae8a06a7d-1365591.515460458
2026-05-13 19:21:37,574 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:21:40,336 INFO reachy_mini_conversation_app.console:674 | role=user content=Factory, software factories, which are called dark factories.
2026-05-13 19:21:41,926 INFO reachy_mini_conversation_app.base_realtime:833 | Tool call received — tool_name='ask_jarvis', call_id=call_475852c6f3d046aa924b53183e2cad0a, is_idle=False, args={"message":"Please do a concise web search on software factories and so-called 'dark factories'. I need a short spoken summary covering what each term means, how they relate, and one or two examples or caveats."}
2026-05-13 19:21:41,926 INFO reachy_mini_conversation_app.tools.background_tool_manager:200 | Started background tool: ask_jarvis (id=call_475852c6f3d046aa924b53183e2cad0a)
2026-05-13 19:21:41,926 INFO reachy_mini_conversation_app.base_realtime:870 | Started background tool: ask_jarvis (id=ask_jarvis-call_475852c6f3d046aa924b53183e2cad0a-1365596.423746791, call_id=call_475852c6f3d046aa924b53183e2cad0a)
2026-05-13 19:21:42,021 INFO reachy_mini_conversation_app.console:674 | role=assistant content=🛠️ Used tool ask_jarvis with args {"message":"Please do a concise web search on software factories and so-called 'dark factories'. I need a short spoken summary covering what each term means, how they relate, and one or two examples or caveats."}. The tool is now running. Tool ID: ask_jarvis-call_475852c6f3d046aa924b53183e2cad0a-1365596.423746791
2026-05-13 19:21:42,522 INFO ask_jarvis:134 | AskJarvisTool: Jarvis responded (487 chars) for adapter=reachy-scholar
2026-05-13 19:21:42,546 INFO reachy_mini_conversation_app.base_realtime:541 | Tool 'ask_jarvis' (id=call_f9f1a47428e941acb47a74eae8a06a7d) executed successfully.
2026-05-13 19:21:42,604 INFO reachy_mini_conversation_app.console:674 | role=assistant content={"response": "I can't do a web search right now \u2014 the Tavily API key isn't configured in this environment.\n\nIf you'd like, I can share what I know from my training data, though that may be out of date. \"Talk Factory\" could refer to a few different things \u2014 there's a UK-based events and conferences company called Talk Factory, and there are also smaller businesses with similar names.\n\nDo you have a specific Talk Factory in mind? That would help me narrow it down or suggest the mos…
2026-05-13 19:21:42,816 INFO reachy_mini_conversation_app.base_realtime:730 | Turn latency: response.created 2500 ms after user transcript
2026-05-13 19:21:45,152 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Jarvis can't do the web search right now because web access isn't configured, but from what it knows, Talk Factory may be a UK events and conferences company. If you want, I can still tell you what I know about software factories or dark factories.
2026-05-13 19:21:45,421 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 5104 ms after user transcript
2026-05-13 19:21:51,198 INFO ask_jarvis:134 | AskJarvisTool: Jarvis responded (1459 chars) for adapter=reachy-scholar
2026-05-13 19:21:51,219 INFO reachy_mini_conversation_app.base_realtime:541 | Tool 'ask_jarvis' (id=call_475852c6f3d046aa924b53183e2cad0a) executed successfully.
2026-05-13 19:21:51,416 INFO reachy_mini_conversation_app.console:674 | role=assistant content={"response": "I can't do a web search right now \u2014 the Tavily API key isn't configured in this environment.\n\nBut I can give you a spoken summary from what I know:\n\n**A software factory** is a development model where software is produced in a standardised, repeatable way \u2014 like an assembly line. You have reusable components, templates, and automated pipelines so that new applications can be built quickly and consistently. Think of it as applying manufacturing principles to code. Exam…
2026-05-13 19:21:55,062 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Jarvis still can't web search right now, but the short version is this: a software factory means building software in a standardized, repeatable, heavily automated way, while a dark factory means a physical manufacturing plant that runs mostly or entirely without people on the floor. They're related by the factory idea of automation and consistency, but one is about producing code and the other is about producing physical goods.
2026-05-13 19:22:27,160 ERROR reachy_mini_conversation_app.moves:658 | Failed to set robot target: Lost connection with the server.
2026-05-13 19:22:28,180 ERROR reachy_mini_conversation_app.moves:658 | Failed to set robot target: Lost connection with the server. (suppressed 50 repeats)
2026-05-13 19:22:34,358 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:22:34,528 INFO reachy_mini_conversation_app.console:674 | role=user content=Noise.
2026-05-13 19:22:35,839 INFO reachy_mini_conversation_app.console:674 | role=assistant content=Fair enough. If you want, I can keep it even simpler.
2026-05-13 19:22:36,139 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 1690 ms after user transcript
2026-05-13 19:22:43,363 INFO reachy_mini_conversation_app.console:631 | User intervention: flushing player queue
2026-05-13 19:22:44,164 INFO reachy_mini_conversation_app.console:674 | role=user content=Yeah, go for it.
2026-05-13 19:22:46,769 INFO reachy_mini_conversation_app.console:674 | role=assistant content=A software factory is basically a system for churning out software quickly using templates, automation, and repeatable steps. A dark factory is a real factory with robots doing nearly everything, often with hardly any humans there.
2026-05-13 19:22:47,000 INFO reachy_mini_conversation_app.base_realtime:819 | Turn latency: first audio delta 2974 ms after user transcript
