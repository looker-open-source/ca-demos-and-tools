import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Stack, IconButton, CircularProgress, 
  Accordion, AccordionSummary, AccordionDetails, Tabs, Tab, Divider 
} from '@mui/material';
import { 
  Close, Refresh, 
  ArrowDropDown, 
  Start, 
  SupportAgent, 
  Comment, 
  Code, 
  SmartToy
} from '@mui/icons-material';
import { useSession } from '../context/SessionContext';
import { apiClient } from '../services/clientService';
import '../App.css'; 

interface RightPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

// --- TYPES ---
interface TraceAttributes {
  "gcp.vertex.agent.llm_request"?: string;
  "gcp.vertex.agent.invocation_id"?: string;
  [key: string]: string | number | undefined;
}

interface TraceItem {
  name: string;
  span_id: string;
  parent_span_id: string | null;
  trace_id: string;
  start_time: number;
  end_time: number;
  attributes: TraceAttributes;
  children?: TraceItem[];
}

interface InteractionGroup {
  traceId: string;
  title: string;
  invocationId: string | null; 
  rootSpans: TraceItem[];
}

interface EventItem {
  id: string;
  timestamp: number;
  content: {
    role: string;
    parts: { text: string }[];
  };
  invocationId?: string;
  partial?: boolean;
  turnComplete?: boolean;
  author?: string;
  actions?: any;
  stateDelta?: any;
  artifactDelta?: any;
  requestedAuthConfigs?: any;
  requestedToolConfirmations?: any;
  title?: string;
}

interface SessionResponse {
  id: string;
  events: EventItem[];
}

const RightPanel = ({ isOpen, onClose }: RightPanelProps) => {
  const { activeSessionId, selectedAgentId, traceRefreshTrigger } = useSession();
  
  const [tabIndex, setTabIndex] = useState(0);
  const [interactions, setInteractions] = useState<InteractionGroup[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const [expandedEventId, setExpandedEventId] = useState<string | false>(false);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabIndex(newValue);
  };

  const fetchData = async () => {
    if (!activeSessionId || !selectedAgentId) return;
    setIsLoading(true);
    
    try {
      if (tabIndex === 0) {
        const response: SessionResponse = await apiClient.get(
          `/apps/${selectedAgentId}/users/user/sessions/${activeSessionId}`
        );
        if (response && Array.isArray(response.events)) {
          const filteredEvents = response.events
            .filter(evt => evt.content.role !== 'user') 
            .sort((a, b) => b.timestamp - a.timestamp);
          setEvents(filteredEvents);
        } else {
          setEvents([]);
        }
      } else {
        const response = await apiClient.get(`/debug/trace/session/${activeSessionId}`);
        if (Array.isArray(response)) {
          processTraces(response);
        } else {
          setInteractions([]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch data", err);
      setEvents([]);
      setInteractions([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEventExpand = (eventId: string) => (event: React.SyntheticEvent, isExpanded: boolean) => {
    setExpandedEventId(isExpanded ? eventId : false);
  };

  useEffect(() => {
    if (isOpen && activeSessionId) {
      fetchData();
    }
  }, [isOpen, activeSessionId, tabIndex, traceRefreshTrigger]);

  const processTraces = (rawTraces: any[]) => {
    const traces: TraceItem[] = rawTraces.map(t => ({
      ...t,
      span_id: String(t.span_id),
      parent_span_id: t.parent_span_id ? String(t.parent_span_id) : null,
      trace_id: String(t.trace_id),
      children: []
    }));

    const groups: { [key: string]: TraceItem[] } = {};
    traces.forEach(t => {
      if (!groups[t.trace_id]) groups[t.trace_id] = [];
      groups[t.trace_id].push(t);
    });

    const parsedInteractions: InteractionGroup[] = Object.keys(groups).map(traceId => {
      const groupSpans = groups[traceId];
      const spanMap = new Map<string, TraceItem>();
      
      groupSpans.forEach(span => spanMap.set(span.span_id, { ...span, children: [] }));
      
      const rootSpans: TraceItem[] = [];
      spanMap.forEach(span => {
        if (span.parent_span_id && spanMap.has(span.parent_span_id)) {
          spanMap.get(span.parent_span_id)!.children!.push(span);
        } else {
          rootSpans.push(span);
        }
      });

      let title = "System Event"; 
      const llmSpan = groupSpans.find(s => s.attributes && s.attributes["gcp.vertex.agent.llm_request"]);
      
      if (llmSpan && llmSpan.attributes["gcp.vertex.agent.llm_request"]) {
        try {
          const requestJson = JSON.parse(llmSpan.attributes["gcp.vertex.agent.llm_request"]);
          if (requestJson.contents && Array.isArray(requestJson.contents)) {
            const userContents = requestJson.contents.filter((c: any) => c.role === 'user');
            const lastUserContent = userContents[userContents.length - 1];
            if (lastUserContent?.parts?.[0]?.text) {
              title = lastUserContent.parts[0].text;
            }
          }
        } catch (e) { console.error("Error parsing LLM request", e); }
      } else {
        title = rootSpans[0]?.name || "Interaction";
      }

      const invSpan = groupSpans.find(s => s.attributes && s.attributes["gcp.vertex.agent.invocation_id"]);
      const invocationId = invSpan ? (invSpan.attributes["gcp.vertex.agent.invocation_id"] as string) : null;

      return { traceId, title, invocationId, rootSpans };
    });

    setInteractions(parsedInteractions.reverse());
  };

  const calculateDuration = (start: number, end: number) => {
    const ms = (end - start) / 1000000;
    return `${ms.toFixed(2)}ms`;
  };

  const formatTimestamp = (ts: number) => {
    return new Date(ts * 1000).toLocaleString();
  };

  const getIcon = (name: string) => {
    const iconProps = { fontSize: 'medium' as const, sx: { color: 'var(--text-secondary)', fontSize: '1.5rem' } };
    if (name.includes("invocation")) return <Start {...iconProps} />; 
    if (name.includes("agent")) return <SupportAgent {...iconProps} />; 
    if (name.includes("llm")) return <Comment {...iconProps} />;
    return <Code {...iconProps} />;
  };

  const renderTree = (node: TraceItem) => (
    <Box key={node.span_id} sx={{ mb: 1.5, width: '100%' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ width: '100%' }}>
        <Stack direction="row" alignItems="center" spacing={1.5} sx={{ overflow: 'hidden', flexGrow: 1, mr: 2 }}>
          {getIcon(node.name)}
          <Typography variant="body2" className="dashboard-text" sx={{ fontWeight: 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {node.name}
          </Typography>
        </Stack>
        <Box sx={{ bgcolor: '#e3f2fd', color: '#1967d2', borderRadius: '4px', px: 1.5, py: 0.5, fontSize: '0.8rem', fontWeight: 500, minWidth: '90px', textAlign: 'left', flexShrink: 0 }}>
          {calculateDuration(node.start_time, node.end_time)}
        </Box>
      </Stack>
      {node.children && node.children.length > 0 && (
        <Box sx={{ pl: 3.5, mt: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {node.children.map(child => renderTree(child))}
        </Box>
      )}
    </Box>
  );

  return (
    <Box className={`right-panel-container ${isOpen ? 'open' : ''}`}>
      
      {/* Header */}
      <Box className="right-panel-header">
         <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ height: '100%' }}>
           <Tabs 
              value={tabIndex} 
              onChange={handleTabChange} 
              sx={{ minHeight: '48px', '& .MuiTabs-indicator': { backgroundColor: '#1976d2', height: '3px' } }}
           >
             <Tab label="Events" sx={{ textTransform: 'none', fontWeight: 500, fontSize: '0.95rem', minWidth: '80px', color: 'var(--text-secondary)', '&.Mui-selected': { color: '#1976d2' } }} />
             <Tab label="Trace" sx={{ textTransform: 'none', fontWeight: 500, fontSize: '0.95rem', minWidth: '80px', color: 'var(--text-secondary)', '&.Mui-selected': { color: '#1976d2' } }} />
           </Tabs>
         </Stack>
      </Box>
      
      {/* Content */}
      <Box className="right-panel-content" sx={{ height: 'calc(100% - 49px)', overflowY: 'auto', p: 0 }}>
        {!activeSessionId ? (
           <Box sx={{ textAlign: 'center', mt: 8, color: 'var(--text-secondary)' }}><Typography variant="body2">Select a session to view details.</Typography></Box>
        ) : isLoading ? (
           <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}><CircularProgress size={24} /></Box>
        ) : (
          <>
            {/* --- EVENTS TAB --- */}
            {tabIndex === 0 && (
              events.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'left' }}>
                   <img src="/Icon.png" alt="No Data" style={{ width: '120px', opacity: 0.5, marginBottom: '16px' }} />
                   <Typography variant="body2" color="text.secondary">No events found</Typography>
                </Box>
              ) : (
                <Box sx={{ padding: '1rem', textAlign: 'left' }}>
                  {events.map((evt) => {
                    const mainText = evt.content.parts?.[0]?.text || "No content";
                    return (
                      <Accordion 
                        key={evt.id} 
                        disableGutters 
                        elevation={0} 
                        square
                        expanded={expandedEventId === evt.id}
                        onChange={handleEventExpand(evt.id)}
                        sx={{ 
                          borderTop: '1px solid var(--border-color)', 
                          borderLeft: '1px solid var(--border-color)', 
                          borderRight: '1px solid var(--border-color)', 
                          backgroundColor: 'var(--bg-paper)',
                          '&:before': { display: 'none' },
                          '&:last-child': { borderBottom: '1px solid var(--border-color)'}
                        }}
                      >
                        <AccordionSummary 
                          expandIcon={<ArrowDropDown sx={{ color: 'var(--text-secondary)' }} />} 
                          sx={{ 
                            px: 2, 
                            minHeight: '56px',
                            '& .MuiAccordionSummary-content': { margin: '12px 0' },
                            '&:hover': { backgroundColor: 'var(--side-panel-hover)' }
                          }}
                        >
                          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ width: '100%' }}>
                             <Typography variant="body2" sx={{ fontWeight: 400, color: 'var(--text-primary)' }}>
                               {mainText.length > 50 ? mainText.substring(0, 50) + "..." : mainText}
                             </Typography>
                          </Stack>
                        </AccordionSummary>
                        
                        <AccordionDetails sx={{ px: 2, pb: 2, pt: 0 }}>
                           <Box className="event-details-container">
                              <div style={{ marginBottom: '4px' }}><span className="event-key-label">content</span>:</div>
                              <div style={{ paddingLeft: '16px', marginBottom: '4px' }}><span className="event-key-label">parts</span>:</div>
                              <div style={{ paddingLeft: '32px', marginBottom: '4px' }}>0:</div>
                              <div style={{ paddingLeft: '48px', marginBottom: '4px' }}>
                                <span className="event-value-text">text</span>: <span style={{ color: '#c41d7f' }}>"{mainText}"</span>
                              </div>
                              <div style={{ paddingLeft: '16px', marginBottom: '4px' }}>
                                <span className="event-value-text">role</span>: <span style={{ color: '#c41d7f' }}>"{evt.content.role}"</span>
                              </div>
                              <div style={{ marginBottom: '4px' }}>
                                <span className="event-value-text">partial</span>: <span style={{ color: '#096dd9' }}>{String(evt.partial ?? false)}</span>
                              </div>
                              <div style={{ marginBottom: '4px' }}>
                                <span className="event-value-text">turnComplete</span>: <span style={{ color: '#096dd9' }}>{String(evt.turnComplete ?? false)}</span>
                              </div>
                              <div style={{ marginBottom: '4px' }}>
                                <span className="event-value-text">invocationId</span>: <span style={{ color: '#c41d7f' }}>"{evt.invocationId}"</span>
                              </div>
                              <div style={{ marginBottom: '4px' }}>
                                <span className="event-value-text">author</span>: <span style={{ color: '#c41d7f' }}>"{evt.author || "ConversationalAnalyticsAgent"}"</span>
                              </div>
                              <div style={{ marginBottom: '4px' }}><span className="event-value-text">actions</span>:</div>
                              <div style={{ marginBottom: '4px' }}><span className="event-value-text">stateDelta</span>:</div>
                              <div style={{ marginBottom: '4px' }}><span className="event-value-text">artifactDelta</span>:</div>
                              <div style={{ marginBottom: '4px' }}><span className="event-value-text">requestedAuthConfigs</span>:</div>
                              <div style={{ marginBottom: '4px' }}><span className="event-value-text">requestedToolConfirmations</span>:</div>
                              <div style={{ marginBottom: '4px' }}>
                                <span className="event-value-text">id</span>: <span style={{ color: '#c41d7f' }}>"{evt.id}"</span>
                              </div>
                              <div style={{ marginBottom: '4px' }}>
                                <span className="event-value-text">timestamp</span>: <span style={{ color: '#096dd9' }}>{evt.timestamp}</span>
                              </div>
                              <div>
                                <span className="event-value-text">title</span>: <span style={{ color: '#c41d7f' }}>"text:{mainText}"</span>
                              </div>
                           </Box>
                        </AccordionDetails>
                      </Accordion>
                    );
                  })}
                </Box>
              )
            )}

            {/* --- TRACE TAB --- */}
            {tabIndex === 1 && (
              interactions.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'left' }}>
                   <img src="/Icon.png" alt="No Data" style={{ width: '120px', opacity: 0.5, marginBottom: '16px' }} />
                   <Typography variant="body2" color="text.secondary">No traces found</Typography>
                </Box>
              ) : (
                <Box sx={{ padding: '1rem', textAlign: 'left' }}>
                  {interactions.map((interaction) => (
                    <Accordion 
                      key={interaction.traceId} 
                      disableGutters 
                      elevation={0} 
                      square
                      sx={{ 
                        borderTop: '1px solid var(--border-color)', 
                        borderLeft: '1px solid var(--border-color)', 
                        borderRight: '1px solid var(--border-color)', 
                        backgroundColor: 'var(--bg-paper)',
                        '&:before': { display: 'none' },
                        '&:last-child': { borderBottom: '1px solid var(--border-color)'}
                      }}
                    >
                      <AccordionSummary 
                        expandIcon={<ArrowDropDown sx={{ color: 'var(--text-secondary)' }} />} 
                        sx={{ 
                          px: 2, 
                          minHeight: '56px',
                          '& .MuiAccordionSummary-content': { margin: '12px 0' },
                          '&:hover': { backgroundColor: 'var(--side-panel-hover)' }
                        }}
                      >
                        <Typography variant="body2" sx={{ fontWeight: 400, color: 'var(--text-primary)' }}>
                          {interaction.title}
                        </Typography>
                      </AccordionSummary>
                      
                      <AccordionDetails sx={{ px: 2, pb: 3, pt: 1, textAlign: 'left' }}>
                        <Box sx={{ mb: 2 }}>
                           <Typography variant="body2" className="trace-invocation-text">
                             Invocation ID: <span className="trace-invocation-id">{interaction.invocationId || "N/A"}</span> 
                           </Typography>
                        </Box>
                        {interaction.rootSpans.map(root => renderTree(root))}
                      </AccordionDetails>
                    </Accordion>
                  ))}
                </Box>
              )
            )}
          </>
        )}
      </Box>
    </Box>
  );
};

export default RightPanel;