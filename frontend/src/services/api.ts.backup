/// <reference types="vite/client" />
// API服务层 - 处理所有后端API调用
// 兼容某些类型环境下 ImportMeta 上没有 env 的报错

// 动态API基础URL配置
let currentUserRole: 'doctor' | 'patient' = 'doctor';

const getApiBaseUrl = (): string => {
  const doctorUrl = 'http://localhost:8000/api/v1';
  const patientUrl = 'http://localhost:8001/api/v1';
  
  // 优先使用环境变量
  const envUrl = ((import.meta as any)?.env?.VITE_API_BASE_URL)
    || (typeof (globalThis as any)?.process !== 'undefined' ? (globalThis as any).process?.env?.VITE_API_BASE_URL : undefined);
  
  if (envUrl) {
    return envUrl;
  }
  
  // 根据当前角色返回对应的URL
  return currentUserRole === 'doctor' ? doctorUrl : patientUrl;
};

// 设置用户角色
export const setUserRole = (role: 'doctor' | 'patient') => {
  currentUserRole = role;
};

// 获取当前用户角色
export const getUserRole = (): 'doctor' | 'patient' => {
  return currentUserRole;
};

const API_BASE_URL: string = getApiBaseUrl();

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
    const response = await fetch(`${getApiBaseUrl()}/health`);
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

  try {
    const response = await fetch(`${getApiBaseUrl()}/pdf/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/index/delete`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        department,
        document_type: documentType,
        disease_category: diseaseCategory,
      }),
    });

    return response.json();
  } catch (error) {
    return {
      ok: false,
      message: `删除失败: ${error instanceof Error ? error.message : '未知错误'}`,
    };
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/statistics`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // 转换数据格式
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
      ok: true,
      stores,
    };
  } catch (error) {
    console.error('Failed to fetch knowledge base details:', error);
    return {
      ok: false,
      stores: [],
    };
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/index/rebuild`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        department,
        document_type: documentType,
        disease_category: diseaseCategory,
      }),
    });

    return response.json();
  } catch (error) {
    return {
      ok: false,
      chunks: 0,
      message: `重建失败: ${error instanceof Error ? error.message : '未知错误'}`,
    };
  }
}

// 优化知识库存储
export async function optimizeKnowledgeBase(): Promise<{
  ok: boolean;
  message: string;
  optimized_stores: number;
}> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    return response.json();
  } catch (error) {
    return {
      ok: false,
      message: `优化失败: ${error instanceof Error ? error.message : '未知错误'}`,
      optimized_stores: 0,
    };
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/statistics`);
    return response.json();
  } catch (error) {
    throw new Error(`Failed to fetch medical statistics: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 开始PDF解析
export async function startParse(fileId: string): Promise<{ jobId: string }> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/pdf/parse`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ fileId }),
    });

    if (!response.ok) {
      throw new Error(`Parse failed: ${response.statusText}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(`Parse failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 查询解析状态
export async function getParseStatus(fileId: string): Promise<ParseStatusResponse> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/pdf/status?fileId=${encodeURIComponent(fileId)}`);
    return response.json();
  } catch (error) {
    throw new Error(`Failed to get parse status: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 获取PDF页面图片
export function getPdfPageUrl(fileId: string, page: number, type: 'original' | 'parsed'): string {
  return `${getApiBaseUrl()}/pdf/page?fileId=${encodeURIComponent(fileId)}&page=${page}&type=${type}`;
}

// 获取Citation详情
export async function getCitationChunk(citationId: string): Promise<CitationChunk> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/pdf/chunk?citationId=${encodeURIComponent(citationId)}`);
    return response.json();
  } catch (error) {
    throw new Error(`Failed to get citation chunk: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 构建向量索引
export async function buildIndex(fileId: string): Promise<{ ok: boolean; chunks: number }> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/index/build`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ fileId }),
    });

    if (!response.ok) {
      throw new Error(`Build failed: ${response.statusText}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(`Build failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/index/search`, {
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
  } catch (error) {
    throw new Error(`Search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}


// 自定义SSE处理函数

// 清空聊天会话

// ==================== 医疗知识库 API ====================

// 医疗科室列表
export async function getMedicalDepartments(): Promise<{
  ok: boolean;
  departments: string[];
}> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/departments`);
    return response.json();
  } catch (error) {
    return { ok: false, departments: [] };
  }
}

// 文档类型列表
export async function getDocumentTypes(): Promise<{
  ok: boolean;
  documentTypes: string[];
}> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/document-types`);
    const data = await response.json();
    return {
      ok: data.ok,
      documentTypes: data.document_types || [],
    };
  } catch (error) {
    return { ok: false, documentTypes: [] };
  }
}

// 疾病分类列表
export async function getDiseaseCategories(): Promise<{
  ok: boolean;
  diseaseCategories: string[];
}> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/disease-categories`);
    const data = await response.json();
    return {
      ok: data.ok,
      diseaseCategories: data.disease_categories || [],
    };
  } catch (error) {
    return { ok: false, diseaseCategories: [] };
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/index/build`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fileId,
        department,
        document_type: documentType,
        disease_category: diseaseCategory,
        custom_metadata: customMetadata,
        markdown_content: markdownContent,
      }),
    });

    return response.json();
  } catch (error) {
    throw new Error(`Build medical index failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        k,
        department,
        document_type: documentType,
        disease_category: diseaseCategory,
        score_threshold: scoreThreshold,
      }),
    });

    return response.json();
  } catch (error) {
    throw new Error(`Medical search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
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

  return new EventSource(`${getApiBaseUrl()}/medical/chat?${params.toString()}`);
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
  onMetadata: (metadata: Record<string, any>) => void,
  onDone: (data: { used_retrieval: boolean; safety_checked?: boolean; medical_analysis?: any }) => void,
  onError: (error: string) => void,
  sessionId = 'medical_default',
  department?: string,
  documentType?: string,
  diseaseCategory?: string,
  enableSafetyCheck = true
) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        sessionId,
        department,
        document_type: documentType,
        disease_category: diseaseCategory,
        enable_safety_check: enableSafetyCheck,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body reader available');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() === '') continue;
          
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            if (data === '[DONE]') {
              return;
            }

            try {
              const parsed = JSON.parse(data);
              
              if (parsed.type === 'token') {
                onToken(parsed.content);
              } else if (parsed.type === 'citation') {
                onCitation({
                  citation_id: parsed.citation_id,
                  fileId: parsed.fileId,
                  rank: parsed.rank,
                  page: parsed.page,
                  previewUrl: parsed.previewUrl,
                  snippet: parsed.snippet,
                });
              } else if (parsed.type === 'metadata') {
                onMetadata(parsed.metadata);
              } else if (parsed.type === 'done') {
                onDone({
                  used_retrieval: parsed.used_retrieval,
                  safety_checked: parsed.safety_checked,
                  medical_analysis: parsed.medical_analysis,
                });
                return;
              } else if (parsed.type === 'error') {
                onError(parsed.error);
                return;
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE data:', data, parseError);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error) {
    onError(`Stream error: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/qa`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        sessionId,
        department,
        documentType: documentType,
        diseaseCategory: diseaseCategory,
        enableSafetyCheck: enableSafetyCheck,
        intentRecognitionMethod: intentRecognitionMethod,
        medicalReport: medicalReport,
        reportType: reportType,
      }),
    });

    return response.json();
  } catch (error) {
    return {
      ok: false,
      data: {
        answer: '',
        citations: [],
        metadata: {},
        quality_assessment: null,
        safety_warning: null,
        used_retrieval: false,
        intent: {
          department: '',
          document_type: '',
          disease_category: '',
          confidence: 0,
          reasoning: '',
          method: '',
        },
        session_id: sessionId,
      },
      error: `Medical QA failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
    };
  }
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
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/analyze/symptoms`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        symptoms,
        sessionId,
      }),
    });

    return response.json();
  } catch (error) {
    throw new Error(`Symptom analysis failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 清除医疗聊天会话
export async function clearMedicalSession(sessionId = 'medical_default'): Promise<{
  ok: boolean;
  sessionId: string;
  cleared: boolean;
}> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/medical/chat/clear`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sessionId }),
    });

    return response.json();
  } catch (error) {
    throw new Error(`Clear session failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}