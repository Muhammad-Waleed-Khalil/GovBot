// Backend API configuration
const BACKEND_URL = 'http://localhost:8000';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: Array<{
    id: string;
    title: string;
    url: string;
    snippet: string;
  }>;
}

export interface ChatResponse {
  answer: string;
  documents_retrieved: number;
  sources?: Array<{
    id: string;
    title: string;
    url: string;
    snippet: string;
  }>;
}

export interface ActionRequest {
  query: string;
  context: string;
  action_type: 'feasibility' | 'case_study' | 'executive_report';
}

export interface ActionResponse {
  result: string;
  action_type: string;
}

export const generateResponse = async (message: string, context?: ChatMessage[]): Promise<ChatResponse> => {
  try {
    // Convert ChatMessage[] to backend format if context exists
    const conversationHistory = context ? context.map(msg => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp.toISOString()
    })) : [];

    const response = await fetch(`${BACKEND_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: message,
        conversation_history: conversationHistory
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ChatResponse = await response.json();
    
    // Return the full response with sources
    return data;
  } catch (error) {
    console.error('Error generating response:', error);
    return {
      answer: 'I apologize, but I\'m experiencing technical difficulties. Please try again in a moment or contact the PMRU support team for assistance.',
      documents_retrieved: 0
    };
  }
};

export const generateActionResponse = async (actionType: 'feasibility' | 'case_study' | 'executive_report', query: string, context: string): Promise<string> => {
  try {
    const response = await fetch(`${BACKEND_URL}/action`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query,
        context: context,
        action_type: actionType
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ActionResponse = await response.json();
    return data.result;
  } catch (error) {
    console.error('Error generating action response:', error);
    return 'I apologize, but I\'m experiencing technical difficulties generating the specialized report. Please try again in a moment.';
  }
};