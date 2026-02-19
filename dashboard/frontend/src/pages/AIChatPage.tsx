import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  MessageSquare,
  Send,
  Loader2,
  AlertCircle,
  FileText,
  User,
  Bot,
  Trash2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Copy,
  Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { searchApi } from '@/api/endpoints/search';
import type { ChunkSearchResult } from '@/types';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: ChunkSearchResult[];
  isLoading?: boolean;
}

interface ChatResponse {
  answer: string;
  sources: ChunkSearchResult[];
  tokensUsed?: {
    input: number;
    output: number;
  };
}

const API_BASE = '/api/chat';

async function sendChatMessage(
  message: string,
  history: { role: string; content: string }[]
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/completion`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      history: history.slice(-6), // Last 3 exchanges for context
      maxChunks: 8,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to get AI response');
  }

  return response.json();
}

function SourceCard({ source, index }: { source: ChunkSearchResult; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(source.chunkText || source.snippet || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [source]);

  return (
    <div className="rounded-md border border-border-subtle bg-surface-base overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-surface-overlay transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0 flex items-center justify-center w-5 h-5 rounded bg-accent-blue/20 text-accent-blue text-xs font-medium">
            {index + 1}
          </span>
          <FileText className="h-4 w-4 text-text-tertiary flex-shrink-0" />
          <span className="text-sm text-text-primary truncate">
            {source.eftaNumber || `Document ${source.documentId}`}
          </span>
          {source.pageNumber && (
            <span className="text-xs text-text-tertiary flex-shrink-0">
              p.{source.pageNumber}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-3 border-t border-border-subtle">
          {source.filePath && (
            <div className="mt-2 text-xs text-accent-blue font-mono bg-surface-sunken px-2 py-1 rounded truncate">
              {source.filePath.split('/').pop() || source.filePath}
            </div>
          )}
          <div className="mt-2 text-xs text-text-secondary whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto">
            {source.chunkText || source.snippet}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex flex-col gap-1">
              {source.documentTitle && (
                <span className="text-xs text-text-tertiary truncate max-w-[200px]">
                  {source.documentTitle}
                </span>
              )}
              {source.documentType && (
                <span className="text-xs text-text-disabled">
                  Type: {source.documentType}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary"
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
              <a
                href={`/documents?id=${source.documentId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-accent-blue hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
                View
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ChatMessageComponent({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full',
          isUser ? 'bg-accent-blue/20' : 'bg-accent-purple/20'
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-accent-blue" />
        ) : (
          <Bot className="h-4 w-4 text-accent-purple" />
        )}
      </div>
      <div className={cn('flex-1 min-w-0', isUser && 'flex flex-col items-end')}>
        <div
          className={cn(
            'rounded-lg px-4 py-3 max-w-[85%]',
            isUser
              ? 'bg-accent-blue/20 text-text-primary'
              : 'bg-surface-overlay text-text-primary'
          )}
        >
          {message.isLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm text-text-secondary">Thinking...</span>
            </div>
          ) : (
            <div className="text-sm whitespace-pre-wrap">{message.content}</div>
          )}
        </div>

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 w-full max-w-[85%] space-y-2">
            <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
              Sources ({message.sources.length})
            </p>
            {message.sources.map((source, idx) => (
              <SourceCard key={source.chunkId} source={source} index={idx} />
            ))}
          </div>
        )}

        <span className="mt-1 text-xs text-text-tertiary">
          {message.timestamp.toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}

export function AIChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Check if chunk search is available
  const { data: chunkStats, isLoading: statsLoading } = useQuery({
    queryKey: ['chunk-stats'],
    queryFn: searchApi.chunkStats,
  });

  const chatMutation = useMutation({
    mutationFn: ({
      message,
      history,
    }: {
      message: string;
      history: { role: string; content: string }[];
    }) => sendChatMessage(message, history),
    onSuccess: (data) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.isLoading
            ? {
                ...msg,
                content: data.answer,
                sources: data.sources,
                isLoading: false,
              }
            : msg
        )
      );
    },
    onError: (error: Error) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.isLoading
            ? {
                ...msg,
                content: `Error: ${error.message}`,
                isLoading: false,
              }
            : msg
        )
      );
    },
  });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmedInput = inputValue.trim();
      if (!trimmedInput || chatMutation.isPending) return;

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: trimmedInput,
        timestamp: new Date(),
      };

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setInputValue('');

      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      chatMutation.mutate({ message: trimmedInput, history });
    },
    [inputValue, messages, chatMutation]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit]
  );

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  const isReady = chunkStats && chunkStats.ftsAvailable && chunkStats.totalChunks > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-border-subtle">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-purple/15">
            <MessageSquare className="h-5 w-5 text-accent-purple" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-text-primary">AI Chat</h2>
            <p className="text-sm text-text-secondary">
              Ask questions about the Epstein documents
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={clearChat}
            className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-overlay rounded-md transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            Clear
          </button>
        )}
      </div>

      {/* Status Bar */}
      {statsLoading ? (
        <div className="flex items-center gap-2 py-3 text-sm text-text-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking document index...
        </div>
      ) : !isReady ? (
        <div className="flex items-center gap-3 py-3 px-4 my-4 rounded-lg border border-accent-amber/30 bg-accent-amber/5">
          <AlertCircle className="h-5 w-5 text-accent-amber flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-accent-amber">
              Document Index Not Ready
            </p>
            <p className="text-xs text-text-secondary">
              The document chunking and indexing process needs to complete before AI
              chat is available.
              {chunkStats && ` (${chunkStats.totalChunks.toLocaleString()} chunks indexed)`}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-4 py-2 text-xs text-text-tertiary">
          <span>{chunkStats.totalChunks.toLocaleString()} chunks indexed</span>
          <span>
            {chunkStats.documentsWithChunks.toLocaleString()} documents searchable
          </span>
          {chunkStats.vectorSearchAvailable && (
            <span className="flex items-center gap-1 text-accent-green">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
              Vector search enabled
            </span>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="h-12 w-12 text-text-disabled mb-4" />
            <h3 className="text-lg font-medium text-text-secondary mb-2">
              Start a conversation
            </h3>
            <p className="text-sm text-text-tertiary max-w-md">
              Ask questions about the Epstein documents. The AI will search through
              indexed document chunks to find relevant information and provide
              answers with source citations.
            </p>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
              {[
                'What properties did Epstein own?',
                'Who visited Little St. James island?',
                'What financial transactions involved Deutsche Bank?',
                'Summarize the relationship between Epstein and Maxwell',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setInputValue(suggestion)}
                  disabled={!isReady}
                  className="px-4 py-3 text-sm text-text-secondary bg-surface-overlay hover:bg-surface-sunken rounded-lg border border-border-subtle transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessageComponent key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="pt-4 border-t border-border-subtle">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isReady
                ? 'Ask a question about the documents...'
                : 'Waiting for document index...'
            }
            disabled={!isReady || chatMutation.isPending}
            rows={1}
            className={cn(
              'w-full resize-none rounded-lg border border-border-subtle bg-surface-base',
              'px-4 py-3 pr-12 text-sm text-text-primary placeholder:text-text-disabled',
              'focus:border-accent-blue focus:outline-none focus:ring-1 focus:ring-accent-blue',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
            style={{ minHeight: '48px', maxHeight: '120px' }}
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || !isReady || chatMutation.isPending}
            className={cn(
              'absolute right-2 top-1/2 -translate-y-1/2',
              'flex items-center justify-center w-8 h-8 rounded-md',
              'bg-accent-blue text-white',
              'hover:bg-accent-blue/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {chatMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="mt-2 text-xs text-text-tertiary text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  );
}
