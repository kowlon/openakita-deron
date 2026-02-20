// ─── WebUIView: Agent 工作流可视化界面 ───
// 三栏布局：左侧会话列表 + 中间步骤卡片 + 右侧详情面板
// 支持 Auto/Edit 模式切换和模型选择

import { useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type {
  AgentSession,
  AgentStep,
  AgentStepStatus,
  AgentStepType,
  ExecutionMode,
  ModelInfo,
  EndpointSummary,
} from "../types";
import { genId, formatTime } from "../utils";
import {
  IconPlus,
  IconSearch,
  IconGear,
  IconCheck,
  IconX,
  IconLoader,
  IconCircle,
  IconChevronDown,
  IconChevronUp,
  IconChevronRight,
  IconCopy,
  IconDownload,
  IconClose,
  IconChat,
  IconTrash,
  IconZap,
  IconBrain,
  IconWrench,
  IconBolt,
  IconLightbulb,
  IconList,
  IconGlobe,
} from "../icons";

// ─── 步骤类型图标映射 ───
function StepTypeIcon({ type, size = 20 }: { type: AgentStepType; size?: number }) {
  switch (type) {
    case "llm":
      return <IconBrain size={size} className="text-blue-400" />;
    case "tool":
      return <IconWrench size={size} className="text-orange-400" />;
    case "skill":
      return <IconBolt size={size} className="text-purple-400" />;
    case "thinking":
      return <IconLightbulb size={size} className="text-yellow-400" />;
    case "planning":
      return <IconList size={size} className="text-green-400" />;
    default:
      return <IconCircle size={size} />;
  }
}

// ─── 步骤状态图标 ───
function StepStatusIcon({ status }: { status: AgentStepStatus }) {
  switch (status) {
    case "pending":
      return (
        <div className="w-8 h-8 rounded-full bg-slate-700/50 text-slate-400 border border-slate-600 flex items-center justify-center">
          <IconCircle size={18} />
        </div>
      );
    case "running":
      return (
        <div className="w-8 h-8 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center animate-pulse">
          <IconLoader size={18} className="animate-spin" />
        </div>
      );
    case "completed":
      return (
        <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-500 border border-emerald-500/30 flex items-center justify-center">
          <IconCheck size={18} />
        </div>
      );
    case "failed":
      return (
        <div className="w-8 h-8 rounded-full bg-red-500/20 text-red-500 border border-red-500/30 flex items-center justify-center">
          <IconX size={18} />
        </div>
      );
  }
}

// ─── 左侧会话列表 ───
type SessionSidebarProps = {
  sessions: AgentSession[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
};

function SessionSidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  searchQuery,
  onSearchChange,
}: SessionSidebarProps) {
  const { t } = useTranslation();

  const filteredSessions = useMemo(() => {
    if (!searchQuery) return sessions;
    const query = searchQuery.toLowerCase();
    return sessions.filter(s => s.title.toLowerCase().includes(query));
  }, [sessions, searchQuery]);

  return (
    <aside className="w-72 bg-[#111722] border-r border-primary/10 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 flex flex-col gap-6">
        <div className="flex flex-col">
          <h1 className="text-white text-lg font-bold leading-normal tracking-tight flex items-center gap-2">
            <IconBrain className="text-primary" size={24} />
            SeeAgent
          </h1>
          <p className="text-[#92a4c9] text-xs font-medium uppercase tracking-widest">AI Orchestrator</p>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewSession}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg h-11 bg-primary text-white text-sm font-bold leading-normal hover:bg-primary/90 transition-colors"
        >
          <IconPlus size={20} />
          <span>{t("webui.newChat") || "New Chat"}</span>
        </button>

        {/* Search */}
        <div className="flex flex-col gap-1">
          <div className="relative flex items-center">
            <IconSearch size={20} className="absolute left-3 text-[#92a4c9]" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => onSearchChange(e.target.value)}
              className="w-full h-10 bg-[#232f48] border-none rounded-lg pl-10 pr-4 text-white placeholder:text-[#92a4c9] text-sm focus:ring-1 focus:ring-primary"
              placeholder={t("webui.searchSessions") || "Search sessions..."}
            />
          </div>
        </div>
      </div>

      {/* Session List */}
      <nav className="flex-1 overflow-y-auto px-2 space-y-1">
        {filteredSessions.map(session => (
          <div
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors group ${
              session.id === currentSessionId
                ? "bg-primary/20 border border-primary/30"
                : "hover:bg-[#232f48]"
            }`}
          >
            <div
              className={`flex items-center justify-center rounded-lg shrink-0 size-10 ${
                session.id === currentSessionId ? "bg-primary text-white" : "bg-[#232f48] group-hover:bg-[#314161] text-white"
              }`}
            >
              <IconChat size={20} />
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <p className={`text-sm font-semibold truncate ${session.id === currentSessionId ? "text-white" : "text-slate-300"}`}>
                {session.title}
              </p>
              <p className="text-[#92a4c9] text-xs truncate">
                {session.steps.length} steps • {formatRelativeTime(session.timestamp)}
              </p>
            </div>
            <button
              onClick={e => {
                e.stopPropagation();
                onDeleteSession(session.id);
              }}
              className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
            >
              <IconTrash size={16} />
            </button>
          </div>
        ))}
      </nav>

      {/* Bottom */}
      <div className="p-4 border-t border-[#232f48]">
        <div className="flex items-center gap-3 px-3 py-2 text-[#92a4c9] hover:text-white hover:bg-[#232f48] rounded-lg cursor-pointer transition-colors">
          <IconGear size={18} />
          <span className="text-sm font-medium">{t("webui.settings") || "Settings"}</span>
        </div>
      </div>
    </aside>
  );
}

// ─── 步骤卡片组件 ───
type StepCardProps = {
  step: AgentStep;
  index: number;
  isLast: boolean;
  isSelected: boolean;
  isExpanded: boolean;
  onSelect: () => void;
  onToggleExpand: () => void;
};

function StepCard({
  step,
  index,
  isLast,
  isSelected,
  isExpanded,
  onSelect,
  onToggleExpand,
}: StepCardProps) {
  const typeLabels: Record<AgentStepType, string> = {
    llm: "LLM Processing",
    tool: "Tool Execution",
    skill: "Skill Execution",
    thinking: "Thinking",
    planning: "Planning",
  };

  const typeLabelsCN: Record<AgentStepType, string> = {
    llm: "LLM 调用",
    tool: "工具调用",
    skill: "技能调用",
    thinking: "思考",
    planning: "规划",
  };

  return (
    <div className="flex gap-4">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <StepStatusIcon status={step.status} />
        {!isLast && <div className="w-0.5 flex-1 bg-emerald-500/20 my-2" />}
      </div>

      {/* Card content */}
      <div className="flex-1 pb-4">
        <div
          onClick={onSelect}
          className={`rounded-xl p-4 transition-all cursor-pointer group ${
            isSelected
              ? "bg-background-dark border-2 border-primary shadow-lg"
              : "bg-background-dark border border-primary/10 hover:border-primary/40 shadow-sm"
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${isSelected ? "bg-primary/20" : "bg-slate-800"}`}>
                <StepTypeIcon type={step.type} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white">
                  Step {index + 1}: {step.title}
                </h4>
                <p className="text-xs text-slate-400">
                  {typeLabelsCN[step.type]} • {step.duration ? `${(step.duration / 1000).toFixed(1)}s` : "..."}
                </p>
              </div>
            </div>
            <button
              onClick={e => {
                e.stopPropagation();
                onToggleExpand();
              }}
              className="text-slate-500 hover:text-primary transition-colors"
            >
              {isExpanded ? <IconChevronUp size={20} /> : <IconChevronDown size={20} />}
            </button>
          </div>

          {/* Expanded summary */}
          {isExpanded && step.summary && (
            <div className="mt-4 p-3 bg-slate-900/50 rounded-lg text-xs leading-relaxed text-slate-300">
              <p className="font-medium text-primary mb-1">执行结果:</p>
              {step.summary}
            </div>
          )}

          {/* Running progress */}
          {step.status === "running" && step.progress && (
            <div className="mt-4 p-3 bg-slate-900/50 rounded-lg">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span>{step.progress.stage}</span>
                <span>{step.progress.message}</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all"
                  style={{ width: `${(step.progress.current / step.progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Running dots animation */}
          {step.status === "running" && !step.progress && (
            <div className="mt-4 flex justify-end">
              <div className="flex space-x-1">
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" />
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]" />
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 右侧详情面板 ───
type DetailPanelProps = {
  step: AgentStep | null;
  onClose: () => void;
};

function DetailPanel({ step, onClose }: DetailPanelProps) {
  const { t } = useTranslation();

  if (!step) return null;

  const handleCopyJson = (data: Record<string, unknown>) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
  };

  const statusColors: Record<AgentStepStatus, string> = {
    pending: "bg-slate-500/10 text-slate-400 border-slate-500/20",
    running: "bg-primary/10 text-primary border-primary/20",
    completed: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    failed: "bg-red-500/10 text-red-500 border-red-500/20",
  };

  const typeColors: Record<AgentStepType, string> = {
    llm: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    tool: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    skill: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    thinking: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    planning: "bg-green-500/10 text-green-400 border-green-500/20",
  };

  const typeLabelsCN: Record<AgentStepType, string> = {
    llm: "LLM 调用",
    tool: "工具",
    skill: "技能",
    thinking: "思考",
    planning: "规划",
  };

  return (
    <aside className="w-96 bg-[#111722] border-l border-primary/10 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <header className="h-16 border-b border-primary/10 flex items-center justify-between px-5 bg-[#111722]/80">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <IconList size={20} className="text-primary" />
          {t("webui.stepDetails") || "步骤详情"}
        </h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
          <IconClose size={20} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        {/* Metadata */}
        <section className="p-5 border-b border-primary/10">
          <div className="flex flex-wrap gap-2 mb-4">
            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide border ${statusColors[step.status]}`}>
              {step.status === "completed" ? "成功" : step.status === "failed" ? "失败" : step.status === "running" ? "执行中" : "等待中"}
            </span>
            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide border ${typeColors[step.type]}`}>
              {typeLabelsCN[step.type]}
            </span>
            <span className="px-2 py-1 rounded bg-slate-800 text-slate-400 text-[10px] font-bold uppercase tracking-wide">
              ID: {step.id.slice(0, 8)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">开始时间</p>
              <p className="text-xs text-white">{formatTime(step.startTime)}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">结束时间</p>
              <p className="text-xs text-white">{step.endTime ? formatTime(step.endTime) : "-"}</p>
            </div>
            <div className="col-span-2">
              <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">执行时长</p>
              <p className="text-xs text-white font-mono">{step.duration ? `${step.duration.toLocaleString()}ms (${(step.duration / 1000).toFixed(1)}s)` : "-"}</p>
            </div>
          </div>
        </section>

        {/* Input */}
        {step.input && Object.keys(step.input).length > 0 && (
          <section className="p-5 border-b border-primary/10">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-bold text-slate-200 uppercase tracking-wider">输入参数</p>
              <button
                onClick={() => handleCopyJson(step.input!)}
                className="text-primary text-[10px] font-bold flex items-center gap-1 hover:underline"
              >
                <IconCopy size={14} />
                复制 JSON
              </button>
            </div>
            <div className="bg-black/40 rounded-lg p-3 font-mono text-[11px] text-primary/80 leading-relaxed overflow-x-auto">
              <pre>{JSON.stringify(step.input, null, 2)}</pre>
            </div>
          </section>
        )}

        {/* Output */}
        <section className="p-5">
          <p className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-4">输出结果</p>

          {step.output && (
            <div className="prose prose-invert prose-sm mb-4">
              <p className="text-xs text-slate-300 whitespace-pre-wrap">{step.output}</p>
            </div>
          )}

          {step.outputData && (
            <div className="bg-black/40 rounded-lg p-3 font-mono text-[11px] text-primary/80 leading-relaxed overflow-x-auto">
              <pre>{JSON.stringify(step.outputData, null, 2)}</pre>
            </div>
          )}

          {step.error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
              <p className="font-bold mb-1">错误信息:</p>
              <p>{step.error}</p>
            </div>
          )}

          <button className="w-full mt-6 py-2 border border-slate-700 rounded text-[11px] font-bold text-slate-400 hover:text-white hover:border-slate-500 transition-all flex items-center justify-center gap-2">
            <IconDownload size={16} />
            下载完整输出
          </button>
        </section>
      </div>
    </aside>
  );
}

// ─── 模型选择器 ───
type ModelSelectorProps = {
  models: ModelInfo[];
  currentModel: string | null;
  onSelectModel: (modelId: string) => void;
  endpoints?: EndpointSummary[];
};

function ModelSelector({ models, currentModel, onSelectModel, endpoints = [] }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  // 如果有 endpoints，优先使用
  const displayModels = endpoints.length > 0
    ? endpoints.map(ep => ({
        id: ep.name,
        name: `${ep.model} (${ep.name})`,
        provider: ep.provider,
      }))
    : models;

  const currentModelInfo = displayModels.find(m => m.id === currentModel) || displayModels[0];

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-[11px] text-slate-500 hover:text-slate-300 flex items-center gap-1"
      >
        <IconZap size={14} />
        {currentModelInfo?.name || "选择模型"}
        <IconChevronDown size={12} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-50">
          <div className="p-2 border-b border-slate-700">
            <p className="text-[10px] text-slate-500 font-bold uppercase">选择模型</p>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {displayModels.map(model => (
              <button
                key={model.id}
                onClick={() => {
                  onSelectModel(model.id);
                  setIsOpen(false);
                }}
                className={`w-full px-3 py-2 text-left text-xs hover:bg-slate-700 transition-colors ${
                  model.id === currentModel ? "bg-primary/20 text-primary" : "text-slate-300"
                }`}
              >
                <p className="font-medium">{model.name}</p>
                <p className="text-[10px] text-slate-500">{model.provider}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── 模式切换 ───
type ModeSwitcherProps = {
  mode: ExecutionMode;
  onModeChange: (mode: ExecutionMode) => void;
};

function ModeSwitcher({ mode, onModeChange }: ModeSwitcherProps) {
  return (
    <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
      <button
        onClick={() => onModeChange("auto")}
        className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
          mode === "auto" ? "bg-primary text-white" : "text-slate-400 hover:text-white"
        }`}
      >
        Auto
      </button>
      <button
        onClick={() => onModeChange("edit")}
        className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
          mode === "edit" ? "bg-primary text-white" : "text-slate-400 hover:text-white"
        }`}
      >
        Edit
      </button>
    </div>
  );
}

// ─── 主组件 ───
type WebUIViewProps = {
  endpoints?: EndpointSummary[];
  onSendMessage?: (message: string) => void;
};

export function WebUIView({ endpoints = [], onSendMessage }: WebUIViewProps) {
  const { t } = useTranslation();

  // State
  const [sessions, setSessions] = useState<AgentSession[]>([
    {
      id: "demo-1",
      title: "Web Research Task",
      userMessage: "Research the latest trends in AI agents for 2024. Focus on multi-agent orchestration frameworks.",
      steps: [
        {
          id: "step-1",
          type: "llm",
          status: "completed",
          title: "分析用户需求",
          summary: "已分解查询为4个子任务：研究、分析、综合、报告。",
          startTime: Date.now() - 50000,
          endTime: Date.now() - 49200,
          duration: 800,
          input: { query: "AI multi-agent frameworks 2024" },
          output: "Decomposed query into 4 sub-tasks",
        },
        {
          id: "step-2",
          type: "tool",
          status: "completed",
          title: "网络搜索",
          summary: "已查询 Google Search API，找到12篇相关论文和仓库。",
          startTime: Date.now() - 49000,
          endTime: Date.now() - 46600,
          duration: 2400,
          input: { query: "AI multi-agent frameworks 2024", num_results: 12 },
          outputData: {
            results: [
              { title: "CrewAI Framework Overview", url: "https://example.com/crewai" },
              { title: "Microsoft AutoGen v0.4", url: "https://example.com/autogen" },
            ],
          },
        },
        {
          id: "step-3",
          type: "skill",
          status: "running",
          title: "内容提取",
          summary: "",
          startTime: Date.now() - 1000,
          progress: { stage: "提取中", current: 5, total: 12, message: "Processing result 5 of 12" },
        },
      ],
      timestamp: Date.now() - 60000,
      status: "active",
      mode: "auto",
    },
    {
      id: "demo-2",
      title: "Data Extraction",
      userMessage: "Extract all email addresses from the provided document.",
      steps: [
        {
          id: "step-1",
          type: "llm",
          status: "completed",
          title: "文档分析",
          summary: "已识别文档格式，准备提取邮箱。",
          startTime: Date.now() - 3600000,
          endTime: Date.now() - 3599500,
          duration: 500,
        },
      ],
      timestamp: Date.now() - 3600000,
      status: "completed",
      mode: "auto",
    },
  ]);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>("demo-1");
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [expandedStepIds, setExpandedStepIds] = useState<Set<string>>(new Set(["step-2"]));
  const [searchQuery, setSearchQuery] = useState("");
  const [inputText, setInputText] = useState("");
  const [currentModel, setCurrentModel] = useState<string | null>(endpoints[0]?.name || null);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("auto");

  // Current session
  const currentSession = useMemo(
    () => sessions.find(s => s.id === currentSessionId) || null,
    [sessions, currentSessionId]
  );

  const selectedStep = useMemo(
    () => currentSession?.steps.find(s => s.id === selectedStepId) || null,
    [currentSession, selectedStepId]
  );

  // Callbacks
  const handleNewSession = useCallback(() => {
    const newSession: AgentSession = {
      id: `session-${genId()}`,
      title: "New Chat",
      userMessage: "",
      steps: [],
      timestamp: Date.now(),
      status: "active",
      mode: executionMode,
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    setSelectedStepId(null);
  }, [executionMode]);

  const handleDeleteSession = useCallback((id: string) => {
    setSessions(prev => prev.filter(s => s.id !== id));
    if (currentSessionId === id) {
      setCurrentSessionId(sessions[0]?.id || null);
    }
  }, [currentSessionId, sessions]);

  const handleSelectSession = useCallback((id: string) => {
    setCurrentSessionId(id);
    setSelectedStepId(null);
  }, []);

  const handleToggleExpand = useCallback((stepId: string) => {
    setExpandedStepIds(prev => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  }, []);

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    onSendMessage?.(inputText);
    setInputText("");
  }, [inputText, onSendMessage]);

  return (
    <div className="flex h-full w-full bg-background-dark">
      {/* Left Sidebar - Session List */}
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col bg-background-light dark:bg-background-dark overflow-hidden relative">
        {/* Header */}
        <header className="h-16 border-b border-primary/10 flex items-center justify-between px-6 bg-background-light dark:bg-background-dark/50 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <IconChat size={20} className="text-primary" />
            <h2 className="font-semibold text-slate-200">{currentSession?.title || "New Chat"}</h2>
            {currentSession && (
              <span className="bg-primary/20 text-primary text-[10px] font-bold uppercase px-2 py-0.5 rounded-full">
                {currentSession.status === "active" ? "Active" : currentSession.status}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <ModeSwitcher mode={executionMode} onModeChange={setExecutionMode} />
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {currentSession ? (
            <div className="space-y-8 max-w-2xl">
              {/* User Message */}
              {currentSession.userMessage && (
                <div className="flex justify-end items-start gap-3 ml-12">
                  <div className="bg-primary text-white p-4 rounded-xl rounded-tr-none shadow-lg max-w-[80%]">
                    <p className="text-sm leading-relaxed">{currentSession.userMessage}</p>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-primary shrink-0 flex items-center justify-center">
                    <span className="text-white text-xs">U</span>
                  </div>
                </div>
              )}

              {/* Steps */}
              <div className="space-y-4">
                {currentSession.steps.map((step, index) => (
                  <StepCard
                    key={step.id}
                    step={step}
                    index={index}
                    isLast={index === currentSession.steps.length - 1}
                    isSelected={step.id === selectedStepId}
                    isExpanded={expandedStepIds.has(step.id)}
                    onSelect={() => setSelectedStepId(step.id)}
                    onToggleExpand={() => handleToggleExpand(step.id)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-slate-500">{t("webui.noSession") || "选择或创建一个会话开始"}</p>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-6 bg-background-light dark:bg-background-dark/80 backdrop-blur-xl border-t border-primary/10">
          <div className="max-w-4xl mx-auto relative">
            <div className="flex items-end gap-3 bg-[#1e293b] rounded-xl p-3 border border-slate-700 focus-within:border-primary transition-all">
              <textarea
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                className="flex-1 bg-transparent border-none text-white focus:ring-0 placeholder:text-slate-500 text-sm resize-none py-2"
                placeholder={t("webui.inputPlaceholder") || "输入消息..."}
                rows={2}
              />
              <button
                onClick={handleSend}
                className="bg-primary text-white rounded-lg p-2.5 flex items-center justify-center hover:bg-primary/90 transition-colors shadow-lg"
              >
                <IconZap size={18} />
              </button>
            </div>

            <div className="mt-2 flex items-center justify-between px-2">
              <div className="flex gap-4 items-center">
                <ModelSelector
                  models={[]}
                  currentModel={currentModel}
                  onSelectModel={setCurrentModel}
                  endpoints={endpoints}
                />
                <button className="text-[11px] text-slate-500 hover:text-slate-300 flex items-center gap-1">
                  <IconGlobe size={14} />
                  Web Access
                </button>
              </div>
              <p className="text-[10px] text-slate-600">Enter 发送, Shift+Enter 换行</p>
            </div>
          </div>
        </div>
      </main>

      {/* Right Panel - Step Details */}
      {selectedStep && (
        <DetailPanel step={selectedStep} onClose={() => setSelectedStepId(null)} />
      )}
    </div>
  );
}

// ─── Helper Functions ───

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

export default WebUIView;
