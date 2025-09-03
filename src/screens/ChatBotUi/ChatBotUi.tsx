import { AnimatePresence, motion } from "framer-motion";
import { Send, MessageSquare, Plus, Menu, Trash2, Edit3, Check, X, ChevronLeft, FileText, Users, Globe, HelpCircle, BarChart3, FileBarChart, ClipboardList, MessageCircle, Home,Eye } from "lucide-react";
import React, { useState, useRef, useEffect } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { EGovBotLogo } from "../../components/ui/logo";
import { ChatMessageComponent } from "../../components/ui/chat-message";
import { TypingIndicator } from "../../components/ui/typing-indicator";
import { SiriAnimation } from "../../components/ui/siri-animation";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../../components/ui/dialog";
import { ChatMessage, generateResponse, generateActionResponse } from "../../lib/gemini";

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
}

export const ChatBotUi = (): JSX.Element => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [isSidebarVisible, setIsSidebarVisible] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestions = [
    "How can I apply for a CNIC?",
    "What are the Digital Pakistan initiatives?",
    "How do I access government services online?",
    "Tell me about e-governance services"
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load chat sessions from localStorage on component mount
  useEffect(() => {
    const savedSessions = localStorage.getItem('chatSessions');
    if (savedSessions) {
      const sessions = JSON.parse(savedSessions).map((session: any) => ({
        ...session,
        createdAt: new Date(session.createdAt),
        messages: session.messages.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        }))
      }));
      setChatSessions(sessions);
    }
  }, []);

  // Save chat sessions to localStorage whenever they change
  useEffect(() => {
    if (chatSessions.length > 0) {
      localStorage.setItem('chatSessions', JSON.stringify(chatSessions));
    }
  }, [chatSessions]);

  // Update current session messages when messages change
  useEffect(() => {
    if (currentSessionId && messages.length > 0) {
      setChatSessions(prev => prev.map(session => 
        session.id === currentSessionId 
          ? { ...session, messages: [...messages] }
          : session
      ));
    }
  }, [messages, currentSessionId]);

  const handleSendMessage = async (messageText?: string) => {
    const text = messageText || inputValue.trim();
    if (!text || isLoading) return;

    // Create new session if none exists
    if (!currentSessionId) {
      const newSessionId = Date.now().toString();
      const newSession: ChatSession = {
        id: newSessionId,
        title: text.slice(0, 30) + (text.length > 30 ? '...' : ''),
        messages: [],
        createdAt: new Date()
      };
      setChatSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSessionId);
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await generateResponse(text, messages);
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        sources: response.sources
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I apologize for the technical difficulty. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionResponse = async (action: string, originalMessage: string) => {
    setIsLoading(true);
    
    // Check if the conversation context is too simple for detailed analysis
    const isSimpleChat = () => {
      // If there are no messages yet, it's definitely too simple
      if (messages.length === 0) {
        return true;
      }
      
      // Only check USER messages, not assistant responses
      const userMessages = messages.filter(msg => msg.role === 'user');
      const recentUserMessages = userMessages.slice(-3); // Check last 3 user messages
      const userMessageTexts = recentUserMessages.map(msg => msg.content.toLowerCase());
      
      // Check for simple greetings or casual conversation
      const simplePatterns = [
        /^(hi|hello|hey|good morning|good afternoon|good evening)\b/,
        /^(how are you|what's up|what are you|who are you)\b/,
        /^(thanks|thank you|ok|okay|yes|no)\b/,
        /^.{1,20}$/ // Very short messages
      ];
      
      const hasSimpleContent = userMessageTexts.some(msg => 
        simplePatterns.some(pattern => pattern.test(msg.trim()))
      );
      
      // Check if there's insufficient government/policy related content in USER messages
      const governmentKeywords = [
        'government', 'policy', 'service', 'department', 'ministry', 'public',
        'citizen', 'administration', 'regulation', 'law', 'budget', 'project',
        'initiative', 'reform', 'development', 'infrastructure', 'governance',
        // Disaster management and flood-related terms
        'flood', 'disaster', 'emergency', 'monsoon', 'pdma', 'contingency',
        'preparedness', 'response', 'management', 'kp', 'khyber pakhtunkhwa',
        'chief secretary', 'deputy commissioner', 'district', 'provincial',
        'planning', 'coordination', 'safety', 'vulnerability', 'assessment',
        'mitigation', 'relief', 'rehabilitation', 'damage', 'report', 'advisory'
      ];
      
      const hasGovernmentContent = userMessageTexts.some(msg =>
        governmentKeywords.some(keyword => msg.includes(keyword))
      );
      
      // Check if user is asking for detailed analysis in their messages
      const userConversationText = userMessageTexts.join(' ');
      const isDetailedRequest = userConversationText.includes('detail') || 
                               userConversationText.includes('complete') ||
                               userConversationText.includes('comprehensive') ||
                               userConversationText.includes('analysis') ||
                               userConversationText.includes('insight') ||
                               userConversationText.includes('report');
      
      // Return true (simple chat) if:
      // 1. Has simple content (like greetings) AND
      // 2. No government-related content in user messages AND
      // 3. No detailed analysis request from user
      return hasSimpleContent && !hasGovernmentContent && !isDetailedRequest;
    };
    
    try {
      if (isSimpleChat()) {
        // Provide a helpful message when there's not enough data for analysis
        const insufficientDataMessage: ChatMessage = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `I don't have enough specific government or policy-related information in our conversation to provide a meaningful ${action.replace('_', ' ')} analysis. Please share more details about a specific government service, policy, or initiative you'd like me to analyze, and I'll be happy to help with a detailed ${action.replace('_', ' ')}.`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, insufficientDataMessage]);
      } else {
        const response = await generateActionResponse(
          action as 'feasibility' | 'case_study' | 'executive_report',
          originalMessage,
          messages.map(m => m.content).join('\n') // Use full conversation context
        );
        
        const assistantMessage: ChatMessage = {
          id: Date.now().toString(),
          role: 'assistant',
          content: response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Error generating action response:', error);
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'I apologize for the technical difficulty with the specialized analysis. Please try again.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessionToDelete(sessionId);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteSession = () => {
    if (sessionToDelete) {
      setChatSessions(prev => prev.filter(session => session.id !== sessionToDelete));
      if (currentSessionId === sessionToDelete) {
        setMessages([]);
        setCurrentSessionId(null);
      }
      setDeleteDialogOpen(false);
      setSessionToDelete(null);
    }
  };

  const handleStartEdit = (sessionId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(sessionId);
    setEditingTitle(currentTitle);
  };

  const handleSaveEdit = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (editingTitle.trim()) {
      setChatSessions(prev => prev.map(session => 
        session.id === sessionId 
          ? { ...session, title: editingTitle.trim() }
          : session
      ));
    }
    setEditingSessionId(null);
    setEditingTitle("");
  };

  const handleReturnHome = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(null);
    setEditingTitle("");
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar */}
      <AnimatePresence>
        {isSidebarVisible && (
          <motion.div 
             initial={{ x: -288, opacity: 0 }}
             animate={{ x: 0, opacity: 1 }}
             exit={{ x: -288, opacity: 0 }}
             transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
            className="w-72 bg-gradient-to-b from-gray-100 to-gray-50 backdrop-blur-xl border-r-2 border-gray-300 text-gray-800 flex flex-col shadow-2xl"
          >
        {/* Header */}
        <div className="p-6 border-b border-gray-100/80">
          <motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.3 }}
            className="flex items-center justify-between mb-6"
          >
            <div className="flex items-center gap-3">
              <EGovBotLogo />
            </div>
            <button
              onClick={() => setIsSidebarVisible(false)}
              className="p-2 hover:bg-gray-100/80 rounded-lg transition-colors duration-200"
            >
              <ChevronLeft className="w-5 h-5 text-gray-600" />
            </button>
          </motion.div>
          <motion.div
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.3 }}
          >
            <Button
              onClick={() => {
                setMessages([]);
                setCurrentSessionId(null);
              }}
              className="w-full bg-white/80 hover:bg-white hover:shadow-md text-gray-700 border border-gray-200/60 hover:border-gray-300/60 rounded-xl flex items-center gap-3 py-3 px-4 font-medium transition-all duration-200 ease-out hover:scale-[1.02] active:scale-[0.98]"
            >
              <Plus className="w-4.5 h-4.5" />
              New Chat
            </Button>
          </motion.div>
        </div>
        
        {/* Chat History */}
        <div className="flex-1 p-6 overflow-y-auto" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
          <style>{`
            .sidebar-scroll::-webkit-scrollbar {
              display: none;
            }
          `}</style>
          <div className="text-xs text-gray-500 mb-4 font-medium tracking-wide uppercase">Recent Chats</div>
          <div className="space-y-2">
            {chatSessions.map((session, index) => (
              <motion.div 
                key={session.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 + 0.3, duration: 0.3 }}
                onClick={() => {
                  if (editingSessionId !== session.id) {
                    setCurrentSessionId(session.id);
                    setMessages(session.messages);
                  }
                }}
                className={`group rounded-xl p-4 cursor-pointer transition-all duration-200 ease-out hover:scale-[1.02] active:scale-[0.98] ${
                  currentSessionId === session.id 
                    ? 'bg-blue-50/80 border border-blue-200/60 shadow-sm' 
                    : 'bg-white/60 hover:bg-white/80 hover:shadow-sm border border-transparent hover:border-gray-200/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${
                    currentSessionId === session.id 
                      ? 'bg-blue-100/80 text-blue-600' 
                      : 'bg-gray-100/80 text-gray-600'
                  }`}>
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    {editingSessionId === session.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                              handleSaveEdit(session.id, e as any);
                            } else if (e.key === 'Escape') {
                              handleCancelEdit(e as any);
                            }
                          }}
                          className="flex-1 text-sm font-medium bg-white/80 border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-300"
                          autoFocus
                        />
                        <button
                          onClick={(e) => handleSaveEdit(session.id, e)}
                          className="p-1 text-green-600 hover:bg-green-50 rounded transition-colors"
                        >
                          <Check className="w-3 h-3" />
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <span className="text-sm font-medium truncate block text-gray-800">
                          {session.title}
                        </span>
                        <span className="text-xs text-gray-500 font-normal">
                          {session.createdAt.toLocaleDateString()}
                        </span>
                      </>
                    )}
                  </div>
                  {editingSessionId !== session.id && (
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      <button
                        onClick={(e) => handleStartEdit(session.id, session.title, e)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all duration-200"
                        title="Edit name"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleDeleteSession(session.id, e)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
          {chatSessions.length === 0 && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="text-sm text-gray-400 text-center py-8 font-medium"
            >
              No recent chats
            </motion.div>
          )}
        </div>
        
        {/* Footer */}
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.3 }}
          className="p-6 border-t border-gray-100/80 bg-white/40 backdrop-blur-sm"
        >
          <div className="text-xs text-gray-500 font-medium leading-relaxed">
            Government of KPK<br />
            <span className="text-gray-400">Performance Management & Reforms Unit</span>
          </div>
        </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative">
        {/* Sidebar Toggle Button */}
        <AnimatePresence>
          {!isSidebarVisible && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.2 }}
              onClick={() => setIsSidebarVisible(true)}
              className="absolute top-4 left-4 z-30 p-3 bg-white/90 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200/60 hover:bg-white hover:shadow-xl transition-all duration-200 hover:scale-105"
            >
              <Menu className="w-5 h-5 text-gray-700" />
            </motion.button>
          )}
        </AnimatePresence>
        {/* Logo Watermark */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
          <img 
            src="/ChatGPT Image Sep 1, 2025, 03_05_41 PM.png" 
            alt="Logo Watermark" 
            className="w-[500px] h-[500px] opacity-25 object-contain"
          />
        </div>
        
        {messages.length === 0 ? (
          /* Welcome Screen */
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="flex-1 overflow-y-auto bg-gradient-to-br from-emerald-50/30 to-white relative z-10"
          >
            <div className="max-w-4xl mx-auto p-8 relative">
              {/* Siri Animation - Center */}
               <motion.div 
                 initial={{ scale: 0.8, opacity: 0 }}
                 animate={{ scale: 1, opacity: 1 }}
                 transition={{ delay: 0.2, duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
                 className="flex flex-col items-center mb-12"
               >
                 <div className="relative">
                   <div className="absolute inset-0 bg-gradient-to-br from-blue-400/20 to-purple-600/20 rounded-full blur-xl transform scale-110"></div>
                   <div className="relative">
                     <SiriAnimation width={120} height={120} />
                   </div>
                 </div>
                 <motion.div 
                   initial={{ opacity: 0, y: 15 }}
                   animate={{ opacity: 1, y: 0 }}
                   transition={{ delay: 0.5, duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
                   className="mt-6 text-center"
                 >
                   <div className="text-2xl font-bold text-green-700 mb-4">
                     GovTech
                   </div>
                   <div className="text-xl text-gray-700 font-semibold leading-relaxed">
                     Government of KPK<br />
                     <span className="text-lg text-gray-600 font-medium">Performance Management & Reforms Unit</span>
                   </div>
                 </motion.div>
               </motion.div>

              {/* Modern Compact Action Cards - Horizontal Layout */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.6, ease: "easeOut" }}
                className="mb-8"
              >
                <div className="flex flex-wrap gap-4 justify-center">
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.4, duration: 0.4 }}
                    className="group relative bg-white/90 backdrop-blur-sm p-4 rounded-xl border border-gray-200/60 shadow-lg w-48 h-32"
                  >
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-sm">
                          <BarChart3 className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900 mb-1">Feasibility Simulation</h3>
                        <p className="text-xs text-gray-600 leading-tight">Simulate Before You Decide </p>
                      </div>
                    </div>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5, duration: 0.4 }}
                    className="group relative bg-white/90 backdrop-blur-sm p-4 rounded-xl border border-gray-200/60 shadow-lg w-48 h-32"
                  >
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center shadow-sm">
                          <FileBarChart className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900 mb-1">Comparative Analysis</h3>
                        <p className="text-xs text-gray-600 leading-tight">Compare Strategies, Outcomes & Lessons</p>
                      </div>
                    </div>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.6, duration: 0.4 }}
                    className="group relative bg-white/90 backdrop-blur-sm p-4 rounded-xl border border-gray-200/60 shadow-lg w-48 h-32"
                  >
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-violet-600 rounded-lg flex items-center justify-center shadow-sm">
                          <ClipboardList className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900 mb-1">Executive Summary</h3>
                        <p className="text-xs text-gray-600 leading-tight">Your Report, Simplified for Decision-Making</p>
                      </div>
                    </div>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.7, duration: 0.4 }}
                    className="group relative bg-white/90 backdrop-blur-sm p-4 rounded-xl border border-gray-200/60 shadow-lg w-48 h-32"
                  >
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-amber-600 rounded-lg flex items-center justify-center shadow-sm">
                          <Eye className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-gray-900 mb-1">Future Mirror</h3>
                        <p className="text-xs text-gray-600 leading-tight">See How Today's Decisions May Shape Tomorrow</p>
                      </div>
                    </div>
                  </motion.div>
                </div>
              </motion.div>


            </div>
          </motion.div>
        ) : (
          /* Chat Messages */
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="flex-1 overflow-y-auto bg-gradient-to-b from-gray-50/30 to-white/50 relative z-10"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            <style>{`
              .chat-scroll::-webkit-scrollbar {
                display: none;
              }
            `}</style>
            {/* Home Button */}
            <div className="sticky top-0 z-20 bg-white/80 backdrop-blur-xl border-b border-gray-100/60 p-4">
              <div className="max-w-3xl mx-auto flex justify-between items-center">
                <motion.button
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3 }}
                  onClick={handleReturnHome}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-xl border border-blue-200/60 hover:border-blue-300/60 transition-all duration-200 hover:scale-105 active:scale-95 shadow-sm hover:shadow-md"
                >
                  <Home className="w-4 h-4" />
                  <span className="font-medium text-sm">Return to Home</span>
                </motion.button>
                <div className="text-sm text-gray-500 font-medium">
                  {currentSessionId && chatSessions.find(s => s.id === currentSessionId)?.title}
                </div>
              </div>
            </div>
            <div className="max-w-3xl mx-auto p-6">
              {messages.map((message, index) => (
                <ChatMessageComponent 
                  key={message.id} 
                  message={message} 
                  index={index} 
                  onActionResponse={handleActionResponse}
                />
              ))}
              <AnimatePresence>
                {isLoading && <TypingIndicator />}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>
          </motion.div>
        )}
        
        {/* Input Area */}
        <motion.div 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="border-t border-gray-100/60 bg-white/80 backdrop-blur-xl p-6"
        >
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-4 items-end">
              <div className="flex-1 relative">
                <motion.div
                  whileFocus={{ scale: 1.01 }}
                  className="relative"
                >
                  <Input
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={handleKeyPress}
                    className="w-full p-5 pr-14 border border-gray-200/60 rounded-2xl focus:border-blue-300/60 focus:ring-2 focus:ring-blue-100/60 resize-none bg-white/90 backdrop-blur-sm shadow-sm hover:shadow-md transition-all duration-200 ease-out text-gray-800 placeholder-gray-400 font-medium"
                    placeholder="Ask me anything about government services..."
                    disabled={isLoading}
                  />
                  <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                    <Button 
                      onClick={() => handleSendMessage()}
                      disabled={!inputValue.trim() || isLoading}
                      className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white p-3 rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 ease-out disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
                    >
                      <Send className="w-4.5 h-4.5" />
                    </Button>
                  </div>
                </motion.div>
              </div>
            </div>
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="text-xs text-gray-400 mt-4 text-center font-medium"
            >
              GovTech can make mistakes. Consider checking important information.
            </motion.div>
          </div>
        </motion.div>
      </div>
      
      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Chat</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{chatSessions.find(s => s.id === sessionToDelete)?.title || 'this chat'}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDeleteSession}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};