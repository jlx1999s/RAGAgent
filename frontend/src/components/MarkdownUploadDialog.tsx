import { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { 
  Upload, 
  FileText, 
  Loader2, 
  X, 
  AlertCircle,
  CheckCircle,
  Copy
} from 'lucide-react';
import { toast } from 'sonner';
import { 
  buildMedicalIndex,
  getMedicalDepartments,
  getDocumentTypes,
  getDiseaseCategories
} from '../services/api';

interface MarkdownUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function MarkdownUploadDialog({ open, onOpenChange, onSuccess }: MarkdownUploadDialogProps) {
  const [inputMethod, setInputMethod] = useState<'text' | 'file'>('text');
  const [markdownContent, setMarkdownContent] = useState('');
  const [fileId, setFileId] = useState('');
  const [department, setDepartment] = useState('');
  const [documentType, setDocumentType] = useState('');
  const [diseaseCategory, setDiseaseCategory] = useState('');
  const [customMetadata, setCustomMetadata] = useState('');
  
  const [departments, setDepartments] = useState<string[]>([]);
  const [documentTypes, setDocumentTypes] = useState<string[]>([]);
  const [diseaseCategories, setDiseaseCategoriesData] = useState<string[]>([]);

  // 监控状态变化
  useEffect(() => {
    console.log('departments状态变化:', departments);
  }, [departments]);

  useEffect(() => {
    console.log('documentTypes状态变化:', documentTypes);
  }, [documentTypes]);

  useEffect(() => {
    console.log('diseaseCategories状态变化:', diseaseCategories);
  }, [diseaseCategories]);

  // 监控对话框打开状态
  useEffect(() => {
    console.log('对话框open状态变化:', open);
    if (open) {
      console.log('useEffect检测到对话框打开，加载选项...');
      loadOptions();
    }
  }, [open]);
  
  const [loading, setLoading] = useState(false);
  const [buildStatus, setBuildStatus] = useState<'idle' | 'building' | 'success' | 'error'>('idle');
  const [buildResult, setBuildResult] = useState<any>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 加载选项数据
  const loadOptions = async () => {
    try {
      console.log('开始加载选项数据...');
      const [deptRes, docTypeRes, diseaseCatRes] = await Promise.all([
        getMedicalDepartments(),
        getDocumentTypes(),
        getDiseaseCategories()
      ]);
      
      console.log('API响应:', { deptRes, docTypeRes, diseaseCatRes });
      
      if (deptRes.ok) {
        console.log('设置科室数据:', deptRes.departments);
        setDepartments(deptRes.departments);
        console.log('科室数据设置后的状态:', deptRes.departments);
      }
      if (docTypeRes.ok) {
        console.log('设置文档类型数据:', docTypeRes.documentTypes);
        setDocumentTypes(docTypeRes.documentTypes);
        console.log('文档类型数据设置后的状态:', docTypeRes.documentTypes);
      }
      if (diseaseCatRes.ok) {
        console.log('设置疾病分类数据:', diseaseCatRes.diseaseCategories);
        setDiseaseCategoriesData(diseaseCatRes.diseaseCategories);
        console.log('疾病分类数据设置后的状态:', diseaseCatRes.diseaseCategories);
      }
    } catch (error) {
      console.error('加载选项数据失败:', error);
      toast.error('加载选项数据失败');
    }
  };

  // 处理文件上传
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.md') && !file.name.endsWith('.markdown')) {
      toast.error('请选择 .md 或 .markdown 文件');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setMarkdownContent(content);
      // 从文件名生成fileId（去掉扩展名）
      const fileName = file.name.replace(/\.(md|markdown)$/i, '');
      setFileId(fileName);
    };
    reader.readAsText(file);
  };

  // 生成随机fileId
  const generateFileId = () => {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    return `markdown_${timestamp}_${random}`;
  };

  // 保存markdown内容到后端并构建索引
  const handleSubmit = async () => {
    if (!markdownContent.trim()) {
      toast.error('请输入或上传markdown内容');
      return;
    }

    if (!fileId.trim()) {
      toast.error('请输入文件ID');
      return;
    }

    if (!department || !documentType) {
      toast.error('请选择科室和文档类型');
      return;
    }

    // 验证自定义元数据格式
    let parsedMetadata = undefined;
    if (customMetadata.trim()) {
      try {
        parsedMetadata = JSON.parse(customMetadata);
      } catch (error) {
        toast.error('自定义元数据格式错误，请使用有效的JSON格式');
        return;
      }
    }

    try {
      setLoading(true);
      setBuildStatus('building');

      // 构建索引并传递markdown内容
      const metadata = {
        ...parsedMetadata,
        source: 'markdown_upload',
        uploadTime: new Date().toISOString()
      };
      
      const result = await buildMedicalIndex(
        fileId,
        department,
        documentType,
        diseaseCategory || undefined,
        metadata,
        markdownContent
      );

      setBuildResult(result);
      setBuildStatus('success');
      toast.success(`索引构建成功！处理了 ${result.chunks} 个文档块`);
      onSuccess();
      
    } catch (error) {
      console.error('Failed to upload or build index:', error);
      setBuildStatus('error');
      const errorMessage = error instanceof Error ? error.message : '上传或索引构建失败';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // 重置表单
  const resetForm = () => {
    setMarkdownContent('');
    setFileId('');
    setDepartment('');
    setDocumentType('');
    setDiseaseCategory('');
    setCustomMetadata('');
    setBuildStatus('idle');
    setBuildResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // 当对话框打开时加载选项
  const handleOpenChange = (newOpen: boolean) => {
    console.log('handleOpenChange被调用，newOpen:', newOpen);
    if (newOpen) {
      console.log('对话框打开，开始加载选项...');
      loadOptions();
      if (!fileId) {
        setFileId(generateFileId());
      }
    } else {
      console.log('对话框关闭，重置表单...');
      resetForm();
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl w-full max-h-[90vh] overflow-hidden" aria-describedby="markdown-upload-description">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-3">
            <FileText className="h-6 w-6 text-blue-600" />
            <div>
              <span className="text-xl font-semibold">上传Markdown内容构建索引</span>
              <p id="markdown-upload-description" className="text-sm text-muted-foreground font-normal">
                输入或上传markdown内容，构建医疗知识库索引
              </p>
            </div>
          </DialogTitle>
        </DialogHeader>

          <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 左侧：内容输入 */}
              <div className="space-y-4">
                <div>
                  <Label className="text-base font-medium">内容输入方式</Label>
                  <div className="flex space-x-2 mt-2">
                    <Button
                      variant={inputMethod === 'text' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setInputMethod('text')}
                    >
                      <FileText className="w-4 h-4 mr-2" />
                      文本输入
                    </Button>
                    <Button
                      variant={inputMethod === 'file' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setInputMethod('file')}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      文件上传
                    </Button>
                  </div>
                </div>

                {inputMethod === 'text' ? (
                  <div>
                    <Label htmlFor="markdown-content">Markdown内容</Label>
                    <Textarea
                      id="markdown-content"
                      placeholder="请输入markdown内容..."
                      value={markdownContent}
                      onChange={(e) => setMarkdownContent(e.target.value)}
                      className="min-h-[300px] font-mono text-sm"
                    />
                    <div className="flex justify-between items-center mt-2 text-xs text-muted-foreground">
                      <span>{markdownContent.length} 字符</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setFileId(generateFileId())}
                      >
                        <Copy className="w-3 h-3 mr-1" />
                        生成新ID
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <Label htmlFor="markdown-file">选择Markdown文件</Label>
                    <div className="mt-2">
                      <input
                        ref={fileInputRef}
                        type="file"
                        id="markdown-file"
                        accept=".md,.markdown"
                        onChange={handleFileUpload}
                        className="hidden"
                      />
                      <Button
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full"
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        选择文件
                      </Button>
                    </div>
                    {markdownContent && (
                      <div className="mt-4 p-3 bg-muted rounded-lg">
                        <div className="text-sm text-muted-foreground mb-2">
                          文件内容预览 ({markdownContent.length} 字符)
                        </div>
                        <div className="max-h-32 overflow-y-auto text-xs font-mono bg-background p-2 rounded border">
                          {markdownContent.substring(0, 500)}
                          {markdownContent.length > 500 && '...'}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 右侧：配置选项 */}
              <div className="space-y-4">
                <div>
                  <Label htmlFor="file-id">文件ID *</Label>
                  <input
                    id="file-id"
                    type="text"
                    placeholder="输入唯一的文件ID"
                    value={fileId}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFileId(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    用于标识此文档的唯一ID
                  </p>
                </div>

                <div>
                  <Label htmlFor="department">科室 * (共{departments.length}个选项)</Label>
                  <Select value={department} onValueChange={setDepartment}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择科室" />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.length === 0 ? (
                        <div className="px-2 py-1 text-sm text-muted-foreground">
                          加载中...
                        </div>
                      ) : (
                        departments.map((dept) => {
                          console.log('渲染科室选项:', dept);
                          return (
                            <SelectItem key={dept} value={dept}>
                              {dept}
                            </SelectItem>
                          );
                        })
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="document-type">文档类型 *</Label>
                  <Select value={documentType} onValueChange={setDocumentType}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择文档类型" />
                    </SelectTrigger>
                    <SelectContent>
                      {documentTypes.map((type) => (
                        <SelectItem key={type} value={type}>
                          {type}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="disease-category">疾病分类</Label>
                  <Select value={diseaseCategory} onValueChange={setDiseaseCategory}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择疾病分类（可选）" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">无</SelectItem>
                      {diseaseCategories.map((category) => (
                        <SelectItem key={category} value={category}>
                          {category}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="custom-metadata">自定义元数据</Label>
                  <Textarea
                    id="custom-metadata"
                    placeholder='{"author": "医生姓名", "version": "1.0"}'
                    value={customMetadata}
                    onChange={(e) => setCustomMetadata(e.target.value)}
                    className="text-sm font-mono"
                    rows={3}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    JSON格式的自定义元数据（可选）
                  </p>
                </div>

                {/* 构建状态 */}
                {buildStatus !== 'idle' && (
                  <div className="p-4 rounded-lg border">
                    <div className="flex items-center space-x-2 mb-2">
                      {buildStatus === 'building' && (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                          <span className="text-sm font-medium">正在构建索引...</span>
                        </>
                      )}
                      {buildStatus === 'success' && (
                        <>
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm font-medium text-green-700">构建成功</span>
                        </>
                      )}
                      {buildStatus === 'error' && (
                        <>
                          <AlertCircle className="w-4 h-4 text-red-500" />
                          <span className="text-sm font-medium text-red-700">构建失败</span>
                        </>
                      )}
                    </div>
                    
                    {buildResult && buildStatus === 'success' && (
                      <div className="text-sm text-muted-foreground space-y-1">
                        <div>处理文档块: {buildResult.chunks}</div>
                        <div>科室: {buildResult.department}</div>
                        <div>文档类型: {buildResult.document_type}</div>
                        {buildResult.disease_category && (
                          <div>疾病分类: {buildResult.disease_category}</div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 底部操作栏 */}
          <div className="flex items-center justify-between p-6 border-t bg-muted/30">
            <div className="text-sm text-muted-foreground">
              * 必填字段
            </div>
            <div className="flex space-x-2">
              <Button
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={loading}
              >
                取消
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={loading || !markdownContent.trim() || !fileId.trim() || !department || !documentType}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    构建中...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    构建索引
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
}