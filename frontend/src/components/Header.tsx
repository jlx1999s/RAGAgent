import { useState, useEffect, RefObject } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getMedicalStatistics } from '../services/api';
import { Database, FileText, Building2, Home, Settings } from 'lucide-react';
import { Button } from './ui/button';

interface MedicalStats {
  total_documents: number;
  total_stores: number;
  departments: string[];
  document_types: string[];
}

interface HeaderProps {
  refreshStatsRef: RefObject<(() => void) | undefined>;
}

export function Header({ refreshStatsRef }: HeaderProps) {
  const [stats, setStats] = useState<MedicalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await getMedicalStatistics();
        if (response.ok) {
          setStats({
            total_documents: response.total_documents,
            total_stores: response.total_stores,
            departments: response.departments,
            document_types: response.document_types
          });
        }
      } catch (error) {
        console.error('Failed to fetch medical statistics:', error);
      } finally {
        setLoading(false);
      }
    };

    // 将fetchStats函数赋值给ref，以便外部调用
    refreshStatsRef.current = fetchStats;

    fetchStats();
    // 每30秒刷新一次统计数据
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [refreshStatsRef]);

  return (
    <>
      <header className="p-6 mb-3 relative" style={{ border: 'none' }}>
        <div className="relative flex items-center justify-between">
          {/* Left side - Knowledge Base Stats */}
          <div className="w-48 flex flex-col space-y-2">
            {!loading && stats && (
              <>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <Database className="w-4 h-4" />
                  <span>知识库统计</span>
                </div>
                <div className="flex items-center space-x-2 text-sm">
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span className="text-blue-400 font-medium">{stats.total_documents}</span>
                  <span className="text-muted-foreground">个文档</span>
                </div>
                <div className="flex items-center space-x-2 text-sm">
                  <Building2 className="w-4 h-4 text-green-400" />
                  <span className="text-green-400 font-medium">{stats.departments.length}</span>
                  <span className="text-muted-foreground">个科室</span>
                </div>
              </>
            )}
          </div>
          
          {/* Center - Title and Author on same line */}
          <div className="text-center flex-1">
            <h1 className="text-4xl font-bold tracking-wide" style={{ fontFamily: '"Space Grotesk", system-ui, sans-serif' }}>
              <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent drop-shadow-lg font-bold text-[32px] font-[Rubik_Dirt]">医疗多模态RAG检索系统</span> 
              <span className="text-lg text-muted-foreground/80 tracking-wider font-light" style={{ fontFamily: '"Space Grotesk", system-ui, sans-serif' }}>by </span>
              <span className="text-lg text-gradient-gold font-semibold tracking-wider" style={{ fontFamily: '"Space Grotesk", system-ui, sans-serif' }}>j</span>
            </h1>
          </div>

          {/* Right side - Navigation */}
          <div className="w-48 flex justify-end space-x-2">
            <Button
              variant={location.pathname === '/' ? 'default' : 'outline'}
              size="sm"
              onClick={() => navigate('/')}
              className="flex items-center space-x-2"
            >
              <Home className="w-4 h-4" />
              <span>主页</span>
            </Button>
            <Button
              variant={location.pathname === '/knowledge-base' ? 'default' : 'outline'}
              size="sm"
              onClick={() => navigate('/knowledge-base')}
              className="flex items-center space-x-2"
            >
              <Settings className="w-4 h-4" />
              <span>知识库管理</span>
            </Button>
          </div>
        </div>
      </header>
    </>
  );
}