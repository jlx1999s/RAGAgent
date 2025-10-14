import { useState, useEffect } from 'react';
import { 
  getKnowledgeBaseDetails, 
  deleteMedicalIndex, 
  rebuildMedicalIndex, 
  optimizeKnowledgeBase 
} from '../services/api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Dialog } from './ui/dialog';
import { MarkdownUploadDialog } from './MarkdownUploadDialog';
import { 
  Database, 
  Trash2, 
  RefreshCw, 
  Settings, 
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

  // 删除知识库
  const handleDelete = async (store: KnowledgeStore) => {
    try {
      setActionLoading(`delete-${store.id}`);
      const response = await deleteMedicalIndex(
        store.department,
        store.document_type,
        store.disease_category || undefined
      );
      
      if (response.ok) {
        toast.success('知识库删除成功');
        await loadKnowledgeBases(); // 重新加载数据
      }
    } catch (error) {
      console.error('Failed to delete knowledge base:', error);
      toast.error('删除知识库失败');
    } finally {
      setActionLoading(null);
      setDeleteDialogOpen(false);
      setSelectedStore(null);
    }
  };

  // 重建知识库
  const handleRebuild = async (store: KnowledgeStore) => {
    try {
      setActionLoading(`rebuild-${store.id}`);
      const response = await rebuildMedicalIndex(
        store.department,
        store.document_type,
        store.disease_category || undefined
      );
      
      if (response.ok) {
        toast.success(`知识库重建成功，处理了 ${response.chunks} 个文档块`);
        await loadKnowledgeBases(); // 重新加载数据
      }
    } catch (error) {
      console.error('Failed to rebuild knowledge base:', error);
      toast.error('重建知识库失败');
    } finally {
      setActionLoading(null);
    }
  };

  // 优化所有知识库
  const handleOptimize = async () => {
    try {
      setActionLoading('optimize');
      const response = await optimizeKnowledgeBase();
      
      if (response.ok) {
        toast.success(`优化完成，优化了 ${response.optimized_stores} 个知识库`);
        await loadKnowledgeBases(); // 重新加载数据
      }
    } catch (error) {
      console.error('Failed to optimize knowledge base:', error);
      toast.error('优化知识库失败');
    } finally {
      setActionLoading(null);
    }
  };

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
          
          <Button
            onClick={handleOptimize}
            disabled={actionLoading === 'optimize'}
          >
            {actionLoading === 'optimize' ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Settings className="w-4 h-4 mr-2" />
            )}
            优化存储
          </Button>
        </div>
      </div>

      {/* 统计信息 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card rounded-lg p-4 border">
          <div className="flex items-center space-x-2">
            <Database className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-medium">总知识库数</span>
          </div>
          <p className="text-2xl font-bold mt-2">{stores.length}</p>
        </div>
        
        <div className="bg-card rounded-lg p-4 border">
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-green-500" />
            <span className="text-sm font-medium">总文档数</span>
          </div>
          <p className="text-2xl font-bold mt-2">
            {stores.reduce((sum, store) => sum + store.document_count, 0)}
          </p>
        </div>
        
        <div className="bg-card rounded-lg p-4 border">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="text-sm font-medium">已加载</span>
          </div>
          <p className="text-2xl font-bold mt-2">
            {stores.filter(store => store.is_loaded).length}
          </p>
        </div>
        
        <div className="bg-card rounded-lg p-4 border">
          <div className="flex items-center space-x-2">
            <HardDrive className="w-5 h-5 text-purple-500" />
            <span className="text-sm font-medium">存储大小</span>
          </div>
          <p className="text-2xl font-bold mt-2">
            {formatFileSize(stores.reduce((sum, store) => sum + (store.index_size || 0), 0))}
          </p>
        </div>
      </div>

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
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRebuild(store)}
                      disabled={actionLoading === `rebuild-${store.id}`}
                    >
                      {actionLoading === `rebuild-${store.id}` ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4" />
                      )}
                      <span className="ml-1">重建</span>
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
                      <span className="ml-1">删除</span>
                    </Button>
                  </div>
                </div>
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
                <h3 className="text-lg font-semibold">确认删除</h3>
              </div>
              
              <p className="text-muted-foreground mb-6">
                确定要删除知识库 "{selectedStore.department} - {selectedStore.document_type}" 吗？
                此操作不可撤销，将删除所有相关的索引数据。
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