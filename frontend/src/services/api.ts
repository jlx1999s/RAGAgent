// API服务层 - 处理所有后端API调用
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

export interface PdfUploadResponse {
  fileId: string;
  name: string;
  pages: number;
}

export interface ParseStatusResponse {
  status: 'idle' | 'parsing' | 'ready' | 'error';
  progress: number;
  errorMsg?: string;
}

export interface CitationChunk {
  id: string;
  fileId: string;
  page: number;
  snippet: string;
  bbox: [number, number, number, number];
  previewUrl: string;
}

export interface ChatReference {
  id: number;
  text: string;
  page: number;
  citationId?: string;
  rank?: number;
  snippet?: string;
}

// 健康检查
export async function checkHealth(): Promise<{ status: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error('Health check failed');
    return response.json();
  } catch (error) {
    // 静默抛出错误，让上层处理
    throw new Error('API unavailable');
  }
}

// PDF上传
export async function uploadPdf(file: File, replace = true): Promise<PdfUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('replace', replace.toString());

  const response = await fetch(`${API_BASE_URL}/pdf/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return response.json();
}

// 开始PDF解析
export async function startParse(fileId: string): Promise<{ jobId: string }> {
  const response = await fetch(`${API_BASE_URL}/pdf/parse`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ fileId }),
  });

  if (!response.ok) {
    throw new Error(`Parse start failed: ${response.statusText}`);
  }

  return response.json();
}

// 查询解析状态
export async function getParseStatus(fileId: string): Promise<ParseStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/pdf/status?fileId=${encodeURIComponent(fileId)}`);
  
  if (!response.ok) {
    throw new Error(`Status check failed: ${response.statusText}`);
  }

  return response.json();
}

// 获取PDF页面图片
export function getPdfPageUrl(fileId: string, page: number, type: 'original' | 'parsed'): string {
  return `${API_BASE_URL}/pdf/page?fileId=${encodeURIComponent(fileId)}&page=${page}&type=${type}`;
}

// 获取Citation详情
export async function getCitationChunk(citationId: string): Promise<CitationChunk> {
  const response = await fetch(`${API_BASE_URL}/pdf/chunk?citationId=${encodeURIComponent(citationId)}`);
  
  if (!response.ok) {
    throw new Error(`Citation fetch failed: ${response.statusText}`);
  }

  return response.json();
}

// 构建向量索引
export async function buildIndex(fileId: string): Promise<{ ok: boolean; chunks: number }> {
  const response = await fetch(`${API_BASE_URL}/index/build`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ fileId }),
  });

  if (!response.ok) {
    throw new Error(`Index build failed: ${response.statusText}`);
  }

  return response.json();
}

// 搜索索引
export async function searchIndex(fileId: string, query: string, k = 5): Promise<{
  ok: boolean;
  results: Array<{
    text: string;
    score: number;
    metadata: Record<string, any>;
  }>;
}> {
  const response = await fetch(`${API_BASE_URL}/index/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ fileId, query, k }),
  });

  if (!response.ok) {
    throw new Error(`Search failed: ${response.statusText}`);
  }

  return response.json();
}

// SSE聊天接口
export function createChatStream(
  message: string,
  pdfFileId?: string,
  sessionId = 'default'
): EventSource {
  const body = JSON.stringify({
    message,
    sessionId,
    ...(pdfFileId && { pdfFileId }),
  });

  // 创建一个虚拟的EventSource，因为fetch不能直接处理SSE
  // 我们需要使用真实的EventSource或者自定义实现
  const eventSource = new EventSource(`${API_BASE_URL}/chat`, {
    // 注意：标准EventSource不支持POST，这里需要使用polyfill或自定义实现
  });

  return eventSource;
}

// 自定义SSE处理函数
export async function processChatStream(
  message: string,
  onToken: (text: string) => void,
  onCitation: (citation: { 
    citation_id: string; 
    fileId: string; 
    rank: number; 
    page: number; 
    previewUrl: string;
    snippet?: string;
  }) => void,
  onDone: (data: { used_retrieval: boolean }) => void,
  onError: (error: string) => void,
  pdfFileId?: string,
  sessionId = 'default'
) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        sessionId,
        ...(pdfFileId && { pdfFileId }),
      }),
    });

    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      
      // 处理SSE事件
      const events = buffer.split('\n\n');
      buffer = events.pop() || ''; // 保留最后一个不完整的事件

      for (const event of events) {
        if (!event.trim()) continue;

        const lines = event.split('\n');
        let eventType = '';
        let eventData = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7);
          } else if (line.startsWith('data: ')) {
            eventData = line.substring(6);
          }
        }

        if (eventType && eventData) {
          try {
            const data = JSON.parse(eventData);
            
            switch (eventType) {
              case 'citation':
                onCitation(data);
                break;
              case 'token':
                onToken(data.text);
                break;
              case 'done':
                onDone(data);
                return;
              case 'error':
                onError(data.message || 'Unknown error');
                return;
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', e);
          }
        }
      }
    }
  } catch (error) {
    // 如果API不可用，提供一个模拟响应
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      // 模拟响应以展示界面功能
      const mockResponse = `I understand you're asking about: "${message}".

Since the backend API is not currently available, I'm showing you a demonstration of the interface. 

## Key Features Demonstrated:
- **Markdown rendering**: This response shows how text formatting works
- **Code blocks**: Here's an example:

\`\`\`javascript
// Example code with syntax highlighting
function processDocument(content) {
  return content.split('\\n').map(line => ({
    text: line,
    analysis: performAnalysis(line)
  }));
}
\`\`\`

- **Reference citations**: This would normally include citations like [1] and [2] when connected to a real backend
- **Streaming responses**: Text appears progressively as it would from the AI

To see the full functionality, please start the backend server at \`localhost:8001\` and upload a PDF document.`;

      // 模拟流式响应
      const words = mockResponse.split(' ');
      let currentIndex = 0;
      
      const streamInterval = setInterval(() => {
        if (currentIndex < words.length) {
          onToken(words[currentIndex] + ' ');
          currentIndex++;
        } else {
          clearInterval(streamInterval);
          onDone({ used_retrieval: false });
        }
      }, 50);
      
      return;
    }
    
    onError(error instanceof Error ? error.message : 'Unknown error');
  }
}

// 清空聊天会话
export async function clearSession(sessionId = 'default'): Promise<{
  ok: boolean;
  sessionId: string;
  cleared: boolean;
}> {
  const response = await fetch(`${API_BASE_URL}/chat/clear`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Clear session failed: ${response.statusText}`);
  }

  return response.json();
}

// ==================== 医疗知识库 API ====================

// 医疗科室列表
export async function getMedicalDepartments(): Promise<{
  ok: boolean;
  departments: string[];
}> {
  const response = await fetch(`${API_BASE_URL}/medical/departments`);
  if (!response.ok) {
    throw new Error(`Get departments failed: ${response.statusText}`);
  }
  return response.json();
}

// 文档类型列表
export async function getDocumentTypes(): Promise<{
  ok: boolean;
  documentTypes: string[];
}> {
  const response = await fetch(`${API_BASE_URL}/medical/document-types`);
  if (!response.ok) {
    throw new Error(`Get document types failed: ${response.statusText}`);
  }
  const data = await response.json();
  return {
    ok: data.ok,
    documentTypes: data.document_types || []
  };
}

// 疾病分类列表
export async function getDiseaseCategories(): Promise<{
  ok: boolean;
  diseaseCategories: string[];
}> {
  const response = await fetch(`${API_BASE_URL}/medical/disease-categories`);
  if (!response.ok) {
    throw new Error(`Get disease categories failed: ${response.statusText}`);
  }
  const data = await response.json();
  return {
    ok: data.ok,
    diseaseCategories: data.disease_categories || []
  };
}

// 构建医疗分类索引
export async function buildMedicalIndex(
  fileId: string,
  department: string,
  documentType: string,
  diseaseCategory?: string,
  customMetadata?: Record<string, any>
): Promise<{
  ok: boolean;
  chunks: number;
  department: string;
  document_type: string;
  disease_category?: string;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/index/build`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      fileId,
      department,
      documentType,
      diseaseCategory,
      customMetadata,
    }),
  });

  if (!response.ok) {
    throw new Error(`Medical index build failed: ${response.statusText}`);
  }

  return response.json();
}

// 医疗知识搜索
export async function searchMedicalKnowledge(
  query: string,
  k = 10,
  department?: string,
  documentType?: string,
  diseaseCategory?: string,
  scoreThreshold = 0.0
): Promise<{
  ok: boolean;
  results: Array<{
    text: string;
    score: number;
    metadata: Record<string, any>;
  }>;
  query: string;
  total_found: number;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      k,
      department,
      documentType,
      diseaseCategory,
      scoreThreshold,
    }),
  });

  if (!response.ok) {
    throw new Error(`Medical search failed: ${response.statusText}`);
  }

  return response.json();
}

// 医疗聊天流式响应
export function createMedicalChatStream(
  message: string,
  sessionId = 'medical_default',
  department?: string,
  documentType?: string,
  diseaseCategory?: string,
  enableSafetyCheck = true
): EventSource {
  const params = new URLSearchParams({
    message,
    sessionId,
    enableSafetyCheck: enableSafetyCheck.toString(),
  });

  if (department) params.append('department', department);
  if (documentType) params.append('documentType', documentType);
  if (diseaseCategory) params.append('diseaseCategory', diseaseCategory);

  return new EventSource(`${API_BASE_URL}/medical/chat?${params.toString()}`);
}

// 处理医疗聊天流式响应
export async function processMedicalChatStream(
  message: string,
  onToken: (text: string) => void,
  onCitation: (citation: { 
    citation_id: string; 
    fileId: string; 
    rank: number; 
    page: number; 
    previewUrl: string;
    snippet?: string;
  }) => void,
  onDone: (data: { used_retrieval: boolean; safety_checked?: boolean }) => void,
  onError: (error: string) => void,
  sessionId = 'medical_default',
  department?: string,
  documentType?: string,
  diseaseCategory?: string,
  enableSafetyCheck = true
) {
  const abortController = new AbortController();

  try {
    const response = await fetch(`${API_BASE_URL}/medical/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        sessionId,
        department,
        documentType,
        diseaseCategory,
        enableSafetyCheck,
      }),
      signal: abortController.signal,
    });

    if (!response.ok) {
      throw new Error(`Medical chat failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'token') {
              onToken(data.data);
            } else if (data.type === 'citation') {
              onCitation(data.data);
            } else if (data.type === 'done') {
              onDone(data.data);
              return;
            } else if (data.type === 'error') {
              onError(data.data);
              return;
            }
          } catch (e) {
            console.warn('Failed to parse SSE data:', line);
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return; // 用户主动取消
    }
    onError(error instanceof Error ? error.message : 'Unknown error');
  }

  return abortController;
}

// 症状分析
export async function analyzeSymptoms(
  symptoms: string[],
  sessionId = 'medical_default'
): Promise<{
  ok: boolean;
  symptoms: string[];
  analysis: {
    input_symptoms: string[];
    possible_diseases: Array<{
      disease: string;
      confidence: number;
      matching_symptoms: string[];
      symptom_count: number;
      recommendation: string;
    }>;
    general_recommendations: string[];
  };
}> {
  const response = await fetch(`${API_BASE_URL}/medical/analyze/symptoms`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      symptoms,
      sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Symptom analysis failed: ${response.statusText}`);
  }

  return response.json();
}

// 清除医疗聊天会话
export async function clearMedicalSession(sessionId = 'medical_default'): Promise<{
  ok: boolean;
  sessionId: string;
  cleared: boolean;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/chat/clear`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Clear medical session failed: ${response.statusText}`);
  }

  return response.json();
}