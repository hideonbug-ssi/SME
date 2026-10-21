import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getActiveScenario, switchScenario, type ScenarioName } from '../../api/demo';

type ScenarioConfig = {
  label: string;
  activeClasses: string;
  inactiveClasses: string;
};

const SCENARIOS: Record<Exclude<ScenarioName, 'overdue'>, ScenarioConfig> = {
  green: {
    label: 'Healthy',
    activeClasses: 'text-green-700 bg-green-50 border-green-200 font-semibold',
    inactiveClasses: 'text-gray-500 hover:text-green-700 hover:bg-green-50 border-transparent',
  },
  yellow: {
    label: 'Yellow Alert',
    activeClasses: 'text-amber-700 bg-amber-50 border-amber-200 font-semibold',
    inactiveClasses: 'text-gray-500 hover:text-amber-700 hover:bg-amber-50 border-transparent',
  },
  red: {
    label: 'Critical',
    activeClasses: 'text-red-700 bg-red-50 border-red-200 font-semibold',
    inactiveClasses: 'text-gray-500 hover:text-red-700 hover:bg-red-50 border-transparent',
  },
};

const SCENARIO_ORDER = ['green', 'yellow', 'red'] as const;
const SNAP_PAD = 16;

interface Pos { x: number; y: number }

export function ScenarioSwitcher() {
  const queryClient = useQueryClient();
  const [switching, setSwitching] = useState<ScenarioName | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // null = use default Tailwind positioning; set after first interaction
  const [pos, setPos] = useState<Pos | null>(null);
  const [snapping, setSnapping] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const origin = useRef({ mouseX: 0, mouseY: 0, panelX: 0, panelY: 0 });
  const currentPos = useRef<Pos | null>(null);

  const { data: activeScenario, refetch: refetchScenario } = useQuery({
    queryKey: ['demo', 'scenario'],
    queryFn: getActiveScenario,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });

  // Keep ref in sync so handlers always see latest position
  useEffect(() => { currentPos.current = pos; }, [pos]);

  const snapToEdge = useCallback(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    const snapRight = rect.left + rect.width / 2 > window.innerWidth / 2;
    const snappedX = snapRight
      ? window.innerWidth - rect.width - SNAP_PAD
      : SNAP_PAD;
    const snappedY = Math.max(
      SNAP_PAD,
      Math.min(rect.top, window.innerHeight - rect.height - SNAP_PAD),
    );
    setSnapping(true);
    setPos({ x: snappedX, y: snappedY });
  }, []);

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - origin.current.mouseX;
    const dy = e.clientY - origin.current.mouseY;
    const newX = origin.current.panelX + dx;
    const newY = origin.current.panelY + dy;
    setSnapping(false);
    setPos({ x: newX, y: newY });
  }, []);

  const onMouseUp = useCallback(() => {
    if (!dragging.current) return;
    dragging.current = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    snapToEdge();
  }, [onMouseMove, snapToEdge]);

  function onHeaderMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    if (e.button !== 0) return;
    e.preventDefault();
    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    dragging.current = true;
    origin.current = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      panelX: rect.left,
      panelY: rect.top,
    };
    // Immediately switch from Tailwind fixed pos to explicit coords
    if (currentPos.current === null) {
      setPos({ x: rect.left, y: rect.top });
    }
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  // Re-clamp on window resize so the panel never goes off-screen
  useEffect(() => {
    function onResize() {
      const panel = panelRef.current;
      if (!panel || currentPos.current === null) return;
      const rect = panel.getBoundingClientRect();
      setPos((p) => {
        if (!p) return p;
        return {
          x: Math.max(SNAP_PAD, Math.min(p.x, window.innerWidth - rect.width - SNAP_PAD)),
          y: Math.max(SNAP_PAD, Math.min(p.y, window.innerHeight - rect.height - SNAP_PAD)),
        };
      });
    }
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  async function handleSwitch(name: ScenarioName) {
    if (switching) return;
    setSwitching(name);
    setError(null);
    try {
      await switchScenario(name);
      queryClient.setQueryData(['demo', 'scenario'], name);
      await queryClient.invalidateQueries();
      await queryClient.refetchQueries({ type: 'active' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Switch failed');
      void refetchScenario();
    } finally {
      setSwitching(null);
    }
  }

  const posStyle: React.CSSProperties = pos
    ? {
        position: 'fixed',
        left: pos.x,
        top: pos.y,
        transition: snapping ? 'left 180ms ease, top 180ms ease' : 'none',
      }
    : {};

  return (
    <div
      ref={panelRef}
      className={pos ? 'z-50' : 'fixed bottom-6 right-6 z-50'}
      style={posStyle}
    >
      <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow-md border border-gray-150 overflow-hidden w-40">
        {/* Header — drag handle */}
        <div
          onMouseDown={onHeaderMouseDown}
          className="flex items-center justify-between px-3 py-2 cursor-grab active:cursor-grabbing select-none"
        >
          <span className="text-[10px] font-medium text-gray-400 uppercase tracking-widest">
            Scenarios
          </span>
          <button
            onMouseDown={(e) => e.stopPropagation()}
            onClick={() => setCollapsed((c) => !c)}
            className="text-gray-300 hover:text-gray-500 leading-none transition-colors"
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '＋' : '−'}
          </button>
        </div>

        {/* Error banner */}
        {error && !collapsed && (
          <div className="px-3 py-1.5 border-t border-red-100 text-[10px] text-red-500 truncate">
            {error}
          </div>
        )}

        {/* Buttons — vertical stack */}
        {!collapsed && (
          <div className="px-2 pb-2 flex flex-col gap-1">
            {SCENARIO_ORDER.map((name) => {
              const config = SCENARIOS[name];
              const isActive = activeScenario === name;
              const isLoading = switching === name;

              return (
                <button
                  key={name}
                  onClick={() => handleSwitch(name)}
                  disabled={!!switching}
                  className={[
                    'w-full px-3 py-1.5 rounded-lg text-xs border transition-all duration-150 flex items-center justify-between disabled:opacity-50 disabled:cursor-not-allowed',
                    isActive ? config.activeClasses : config.inactiveClasses,
                  ].join(' ')}
                >
                  <span>{config.label}</span>
                  {isLoading ? (
                    <svg className="animate-spin h-3 w-3 opacity-60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                  ) : isActive ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60 shrink-0" />
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
