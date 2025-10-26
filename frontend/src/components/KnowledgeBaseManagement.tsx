import { useState, useEffect } from 'react';
import { 
  getKnowledgeBaseDetails, 
  deleteMedicalIndex, 
  deleteMedicalDocumentByFileId,
  listDocumentsInStore,
  StoreDocument
} from '../services/api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Dialog } from './ui/dialog';
import { Label } from './ui/label';
import { MarkdownUploadDialog } from './MarkdownUploadDialog';
import { 
  Database, 
  Trash2, 
  RefreshCw, 
  FileText, 
  Calendar,
  HardDrive,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
  Plus
} from 'lucide-react';
import { toast } from 'sonner';

interface KnowledgeStore {
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
}

export function KnowledgeBaseManagement() {
  const [stores, setStores] = useState<KnowledgeStore[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedStore, setSelectedStore] = useState<KnowledgeStore | null>(null);
  const [markdownUploadOpen, setMarkdownUploadOpen] = useState(false);
  // 文档级删除相关状态
  const [docDeleteDialogOpen, setDocDeleteDialogOpen] = useState(false);
  const [docDeleteStore, setDocDeleteStore] = useState<KnowledgeStore | null>(null);
  const [docDeleteFileId, setDocDeleteFileId] = useState('');
  // 文档列表状态
  const [activeStoreId, setActiveStoreId] = useState<string | null>(null);
  const [storeDocs, setStoreDocs] = useState<Record<string, StoreDocument[]>>({});
  const [docListLoadingId, setDocListLoadingId] = useState<string | null>(null);
  
  // 加载知识库数据
  const loadKnowledgeBases = async () => {
    try {
      setLoading(true);
      const response = await getKnowledgeBaseDetails();
      if (response.ok) {
        setStores(response.stores);
      }
    } catch (error) {
      console.error('Failed to load knowledge bases:', error);
      toast.error('加载知识库数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKnowledgeBases();
  }, []);

  // 清空当前知识库
  const handleDelete = async (store: KnowledgeStore) => {
    try {
      setActionLoading(`delete-${store.id}`);
      const response = await deleteMedicalIndex(
        store.department,
        store.document_type,
        store.disease_category || undefined
      );
      
      if (response.ok) {
        toast.success('知识库已清空');
        await loadKnowledgeBases(); // 重新加载数据
      }
    } catch (error) {
      console.error('Failed to clear knowledge base:', error);
      toast.error('清空知识库失败');
    } finally {
      setActionLoading(null);
      setDeleteDialogOpen(false);
      setSelectedStore(null);
    }
  };

  // 文档级删除（增加确认）
  const handleDeleteDocumentConfirmed = async () => {
    if (!docDeleteStore) return;
    const fileId = docDeleteFileId.trim();
    if (!fileId) {
      toast.error('请输入要删除的文档 fileId');
      return;
    }
    try {
      setActionLoading(`doc-delete-${docDeleteStore.id}`);
      const response = await deleteMedicalDocumentByFileId(
        fileId,
        docDeleteStore.department,
        docDeleteStore.document_type,
        docDeleteStore.disease_category || undefined
      );

      if (response.ok) {
        const chunkInfo = typeof response.deleted_chunks === 'number' ? `，删除了 ${response.deleted_chunks} 个文档块` : '';
        toast.success(`文档已删除${chunkInfo}`);
        await loadKnowledgeBases();
      } else {
        toast.error(response.message || '文档删除失败');
      }
    } catch (error) {
      console.error('Failed to delete document:', error);
      toast.error('文档删除失败');
    } finally {
      setActionLoading(null);
      setDocDeleteDialogOpen(false);
      setDocDeleteStore(null);
      setDocDeleteFileId('');
    }
  };

  // 已移除：重建知识库功能

  // 已移除：优化存储功能

  // 格式化文件大小
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  // 格式化日期
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  // 加载某个知识库存储的文档列表
  const loadStoreDocs = async (store: KnowledgeStore) => {
    const key = store.id;
    try {
      setDocListLoadingId(key);
      const res = await listDocumentsInStore(
        store.department,
        store.document_type,
        store.disease_category || undefined
      );
      if (res.ok) {
        setStoreDocs(prev => ({ ...prev, [key]: res.documents }));
        setActiveStoreId(key);
      } else {
        toast.error(res.error || '获取文档列表失败');
      }
    } catch (error) {
      console.error('Failed to load documents in store:', error);
      toast.error('获取文档列表失败');
    } finally {
      setDocListLoadingId(null);
    }
  };

  // 文档列表中的快速删除
  const handleInlineDeleteDoc = async (store: KnowledgeStore, fileId: string) => {
    try {
      setActionLoading(`doc-inline-${store.id}-${fileId}`);
      const response = await deleteMedicalDocumentByFileId(
        fileId,
        store.department,
        store.document_type,
        store.disease_category || undefined
      );
      if (response.ok) {
        toast.success('文档删除成功');
        // 从当前列表移除
        setStoreDocs(prev => ({
          ...prev,
          [store.id]: (prev[store.id] || []).filter(d => d.file_id !== fileId)
        }));
        // 同步刷新统计
        await loadKnowledgeBases();
      } else {
        toast.error(response.message || '文档删除失败');
      }
    } catch (error) {
      console.error('Inline delete doc failed:', error);
      toast.error('文档删除失败');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="ml-2 text-muted-foreground">加载知识库数据...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Database className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold">知识库管理</h1>
            <p className="text-muted-foreground">管理医疗知识库的索引和存储</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            onClick={loadKnowledgeBases}
            disabled={loading}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
          
          <Button
            variant="outline"
            onClick={() => setMarkdownUploadOpen(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            上传Markdown
          </Button>
          
          {/* 已移除：优化存储按钮 */}
        </div>
      </div>

      {/* 统计信息区域已按需求移除，仅保留知识库列表 */}

      {/* 知识库列表 */}
      <div className="bg-card rounded-lg border">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">知识库列表</h2>
        </div>
        <div className="divide-y">
          {stores.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>暂无知识库数据</p>
            </div>
          ) : (
            stores.map((store) => (
              <div key={store.id} className="p-4 hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex-1 space-y-2">
                    {/* 基本信息 */}
                    <div className="flex items-center space-x-3">
                      <h3 className="font-medium">{store.department}</h3>
                      <Badge variant="secondary">{store.document_type}</Badge>
                      {store.disease_category && (
                        <Badge variant="outline">{store.disease_category}</Badge>
                      )}
                      <Badge 
                        variant={store.is_loaded ? "default" : "destructive"}
                        className="flex items-center space-x-1"
                      >
                        {store.is_loaded ? (
                          <CheckCircle className="w-3 h-3" />
                        ) : (
                          <XCircle className="w-3 h-3" />
                        )}
                        <span>{store.is_loaded ? '已加载' : '未加载'}</span>
                      </Badge>
                    </div>
                    
                    {/* 详细信息 */}
                    <div className="flex items-center space-x-6 text-sm text-muted-foreground">
                      <div className="flex items-center space-x-1">
                        <FileText className="w-4 h-4" />
                        <span>{store.document_count} 个文档</span>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        <HardDrive className="w-4 h-4" />
                        <span>{formatFileSize(store.index_size)}</span>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        <Calendar className="w-4 h-4" />
                        <span>更新于 {formatDate(store.last_updated)}</span>
                      </div>
                    </div>
                  </div>
                  {/* 操作按钮 */}
                  <div className="flex items-center space-x-2">
                    {/* 已移除：重建按钮 */}
                    {/* 查看文档列表按钮 */}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => loadStoreDocs(store)}
                      disabled={docListLoadingId === store.id}
                    >
                      {docListLoadingId === store.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <FileText className="w-4 h-4" />
                      )}
                      <span className="ml-1">查看文档</span>
                    </Button>
                    {/* 文档级删除按钮（旧方式） */}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setDocDeleteStore(store);
                        setDocDeleteDialogOpen(true);
                        setDocDeleteFileId('');
                      }}
                      disabled={actionLoading === `doc-delete-${store.id}`}
                      className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                    >
                      {actionLoading === `doc-delete-${store.id}` ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <FileText className="w-4 h-4" />
                      )}
                      <span className="ml-1">删除文档</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedStore(store);
                        setDeleteDialogOpen(true);
                      }}
                      disabled={actionLoading === `delete-${store.id}`}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      {actionLoading === `delete-${store.id}` ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                      <span className="ml-1">清空当前知识库</span>
                    </Button>
                  </div>
                </div>
                {/* 展开文档列表 */}
                {activeStoreId === store.id && (
                  <div className="mt-4 border-t pt-4 space-y-2">
                    {(storeDocs[store.id] || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">此存储暂无文档或加载失败。</p>
                    ) : (
                      (storeDocs[store.id] || []).map((doc) => (
                        <div key={doc.file_id} className="flex items-center justify-between p-2 rounded-md bg-secondary/40">
                          <div className="flex-1">
                            <div className="text-sm font-medium">{doc.title || doc.file_id}</div>
                            <div className="text-xs text-muted-foreground">fileId: {doc.file_id} · 处理时间: {doc.processed_at || '未知'}</div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setDocDeleteStore(store);
                                setDocDeleteFileId(doc.file_id);
                                setDocDeleteDialogOpen(true);
                              }}
                              disabled={actionLoading === `doc-inline-${store.id}-${doc.file_id}`}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              {actionLoading === `doc-inline-${store.id}-${doc.file_id}` ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                              <span className="ml-1">删除</span>
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
      {/* 删除确认对话框 */}
      {deleteDialogOpen && selectedStore && (
        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-card rounded-lg p-6 max-w-md w-full border">
              <div className="flex items-center space-x-3 mb-4">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                <h3 className="text-lg font-semibold">清空当前知识库</h3>
              </div>
              
              <p className="text-muted-foreground mb-6">
                确定要清空知识库 "{selectedStore.department} - {selectedStore.document_type}" 吗？
                此操作将清空该知识库下所有索引与存储数据，操作不可撤销。
              </p>
              
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setDeleteDialogOpen(false);
                    setSelectedStore(null);
                  }}
                >
                  取消
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => handleDelete(selectedStore)}
                  disabled={actionLoading === `delete-${selectedStore.id}`}
                >
                  {actionLoading === `delete-${selectedStore.id}` ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4 mr-2" />
                  )}
                  清空当前知识库
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* 文档级删除对话框 */}
      {docDeleteDialogOpen && docDeleteStore && (
        <Dialog open={docDeleteDialogOpen} onOpenChange={setDocDeleteDialogOpen}>
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-card rounded-lg p-6 max-w-md w-full border">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">文档级删除</h3>
                <p className="text-xs text-muted-foreground mt-1">
                  目标知识库：{docDeleteStore.department} - {docDeleteStore.document_type}{docDeleteStore.disease_category ? ` - ${docDeleteStore.disease_category}` : ''}
                </p>
              </div>

              <div className="space-y-2 mb-6">
                <Label htmlFor="fileId" className="text-sm font-medium">File ID</Label>
                <input
                  id="fileId"
                  type="text"
                  value={docDeleteFileId}
                  onChange={(e) => setDocDeleteFileId(e.target.value)}
                  placeholder="请输入要删除的文档 fileId，例如 qt-001"
                  className="w-full rounded-md border border-border/60 bg-secondary/20 p-2 text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  提示：请确认该 fileId 属于上方所示的知识库分类。
                </p>
              </div>

              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setDocDeleteDialogOpen(false);
                    setDocDeleteStore(null);
                    setDocDeleteFileId('');
                  }}
                >
                  取消
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDeleteDocumentConfirmed}
                  disabled={actionLoading === `doc-delete-${docDeleteStore.id}`}
                >
                  {actionLoading === `doc-delete-${docDeleteStore.id}` ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4 mr-2" />
                  )}
                  确认删除
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* Markdown上传对话框 */}
      <MarkdownUploadDialog
        open={markdownUploadOpen}
        onOpenChange={setMarkdownUploadOpen}
        onSuccess={loadKnowledgeBases}
      />
    </div>
  );
}