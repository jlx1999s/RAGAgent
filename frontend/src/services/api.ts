/// <reference types="vite/client" />
// API服务层 - 处理所有后端API调用
// 兼容某些类型环境下 ImportMeta 上没有 env 的报错
const API_BASE_URL: string = ((import.meta as any)?.env?.VITE_API_BASE_URL)
  || (typeof (globalThis as any)?.process !== 'undefined' ? (globalThis as any).process?.env?.VITE_API_BASE_URL : undefined)
  || 'http://localhost:8000/api/v1';

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

// ==================== 知识库管理 API ====================

// 删除知识库索引
export async function deleteMedicalIndex(
  department: string,
  documentType: string,
  diseaseCategory?: string
): Promise<{
  ok: boolean;
  message: string;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/index/delete`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      department,
      documentType,
      diseaseCategory,
    }),
  });

  if (!response.ok) {
    throw new Error(`Delete medical index failed: ${response.statusText}`);
  }

  return response.json();
}

// 获取知识库详细信息
export async function getKnowledgeBaseDetails(): Promise<{
  ok: boolean;
  stores: Array<{
    id: string;
    department: string;
    document_type: string;
    disease_category: string | null;
    document_count: number;
    created_at: string;
    last_updated: string;
    is_loaded: boolean;
    file_size?: number;
    index_size?: number;
  }>;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/statistics`);
  
  if (!response.ok) {
    throw new Error(`Get knowledge base details failed: ${response.statusText}`);
  }

  const data = await response.json();
  
  // 转换数据格式为管理页面需要的格式
  const stores = Object.entries(data.store_details || {}).map(([id, details]: [string, any]) => ({
    id,
    department: details.department,
    document_type: details.document_type,
    disease_category: details.disease_category,
    document_count: details.document_count,
    created_at: details.created_at,
    last_updated: details.last_updated,
    is_loaded: details.is_loaded,
    file_size: details.file_size,
    index_size: details.index_size,
  }));

  return {
    ok: data.ok,
    stores,
  };
}

// 重建知识库索引
export async function rebuildMedicalIndex(
  department: string,
  documentType: string,
  diseaseCategory?: string
): Promise<{
  ok: boolean;
  chunks: number;
  message: string;
}> {
  // 先删除现有索引
  await deleteMedicalIndex(department, documentType, diseaseCategory);
  
  // 重新构建索引 - 这里需要文件ID，实际实现中可能需要从后端获取
  // 暂时返回模拟数据，实际需要后端提供重建接口
  const response = await fetch(`${API_BASE_URL}/medical/index/rebuild`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      department,
      documentType,
      diseaseCategory,
    }),
  });

  if (!response.ok) {
    throw new Error(`Rebuild medical index failed: ${response.statusText}`);
  }

  return response.json();
}

// 优化知识库存储
export async function optimizeKnowledgeBase(): Promise<{
  ok: boolean;
  message: string;
  optimized_stores: number;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/optimize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Optimize knowledge base failed: ${response.statusText}`);
  }

  return response.json();
}

// 获取医疗知识库统计信息
export async function getMedicalStatistics(): Promise<{
  ok: boolean;
  total_stores: number;
  total_documents: number;
  departments: string[];
  document_types: string[];
  store_details: Record<string, {
    department: string;
    document_type: string;
    disease_category: string | null;
    document_count: number;
    created_at: string;
    last_updated: string;
    is_loaded: boolean;
  }>;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/statistics`);
  
  if (!response.ok) {
    throw new Error(`Get medical statistics failed: ${response.statusText}`);
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


// 自定义SSE处理函数

// 清空聊天会话

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
  customMetadata?: Record<string, any>,
  markdownContent?: string
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
      markdownContent,
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
  // 新增：元数据事件（包含知识图谱增强内容）
  onMetadata: (metadata: Record<string, any>) => void,
  onDone: (data: { used_retrieval: boolean; safety_checked?: boolean; medical_analysis?: any }) => void,
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

    // 兼容后端改为 JSON 返回：如果是 JSON，直接一次性解析并触发回调
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        const result = await response.json();
        if (!result || result.ok === false) {
          onError(result?.error || 'Medical chat failed');
          return abortController;
        }
        const data = result.data || {};
        const answer: string = data.answer || '';
        const citations: any[] = Array.isArray(data.citations) ? data.citations : [];
        const metadata: Record<string, any> | undefined = data.metadata;
        const usedRetrieval: boolean = !!data.used_retrieval;
        const qualityAssessment: any = data.quality_assessment;

        if (answer) {
          onToken(answer);
        }
        for (const c of citations) {
          onCitation({
            citation_id: c.citation_id ?? c.id ?? '',
            fileId: c.fileId ?? '',
            rank: c.rank ?? 0,
            page: c.page ?? 0,
            previewUrl: c.previewUrl ?? '',
            snippet: c.snippet ?? c.text ?? undefined,
          });
        }
        if (metadata) {
          onMetadata(metadata);
        }
        onDone({ used_retrieval: usedRetrieval, safety_checked: !!qualityAssessment, medical_analysis: qualityAssessment });
        return abortController;
      } catch (e) {
        onError(e instanceof Error ? e.message : 'Failed to parse JSON');
        return abortController;
      }
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
            } else if (data.type === 'metadata') {
              onMetadata(data.data);
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

// 非流式医疗问答API
export async function medicalQA(
  message: string,
  sessionId = 'medical_default',
  department?: string,
  documentType?: string,
  diseaseCategory?: string,
  enableSafetyCheck = true,
  intentRecognitionMethod = 'smart',
  medicalReport?: string,
  reportType?: string
): Promise<{
  ok: boolean;
  data: {
    answer: string;
    citations: Array<{
      citation_id: string;
      fileId: string;
      rank: number;
      page: number;
      previewUrl: string;
      snippet?: string;
    }>;
    metadata: Record<string, any>;
    quality_assessment: any;
    safety_warning: any;
    used_retrieval: boolean;
    intent: {
      department: string;
      document_type: string;
      disease_category: string;
      confidence: number;
      reasoning: string;
      method: string;
    };
    session_id: string;
  };
  error?: string;
}> {
  const response = await fetch(`${API_BASE_URL}/medical/qa`, {
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
      intentRecognitionMethod,
      medicalReport,
      reportType,
    }),
  });

  if (!response.ok) {
    throw new Error(`Medical QA failed: ${response.statusText}`);
  }

  return response.json();
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