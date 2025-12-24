import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Stack, IconButton, CircularProgress, 
  Accordion, AccordionSummary, AccordionDetails, Tabs, Tab, Divider 
} from '@mui/material';
import { 
  Close, Refresh, 
  ArrowDropDown, 
  Start, // Changed from Input to Start
  SupportAgent, 
  Comment, // Changed from ChatBubbleOutline to Comment (Chat icon with lines)
  Code, 
  SmartToy, AccountTree, Description, DataObject
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
  graphData?: { dotSrc: string };
  innerTab?: number;
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

  // --- FETCH MAIN LISTS ---
  const fetchData = async () => {
    if (!activeSessionId || !selectedAgentId) return;
    setIsLoading(true);
    
    try {
      if (tabIndex === 0) {
        // Events Tab
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
        // Trace Tab
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

  // --- DRILL DOWN: FETCH DETAILS ON EXPAND ---
  const handleEventExpand = (eventId: string) => async (event: React.SyntheticEvent, isExpanded: boolean) => {
    setExpandedEventId(isExpanded ? eventId : false);

    if (isExpanded && activeSessionId && selectedAgentId) {
      const currentEvent = events.find(e => e.id === eventId);
      if (currentEvent && currentEvent.graphData) return;

      try {
        const graphResponse = await apiClient.get(
          `/apps/${selectedAgentId}/users/user/sessions/${activeSessionId}/events/${eventId}/graph`
        );

        setEvents(prevEvents => prevEvents.map(evt => {
          if (evt.id === eventId) {
            return { ...evt, graphData: graphResponse, innerTab: 0 }; 
          }
          return evt;
        }));

      } catch (err) {
        console.error("Failed to fetch event details", err);
      }
    }
  };

  const handleInnerTabChange = (eventId: string, newValue: number) => {
    setEvents(prev => prev.map(evt => 
      evt.id === eventId ? { ...evt, innerTab: newValue } : evt
    ));
  };

  useEffect(() => {
    if (isOpen && activeSessionId) {
      fetchData();
    }
  }, [isOpen, activeSessionId, tabIndex, traceRefreshTrigger]);

  // --- PROCESSING LOGIC ---
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

  // --- HELPERS ---
  const calculateDuration = (start: number, end: number) => {
    const ms = (end - start) / 1000000;
    return `${ms.toFixed(2)}ms`;
  };

  const formatTimestamp = (ts: number) => {
    return new Date(ts * 1000).toLocaleString();
  };

  // --- UPDATED ICON LOGIC ---
  const getIcon = (name: string) => {
    // INCREASED SIZE: fontSize 'medium' (default 24px) and custom sx '1.5rem'
    const iconProps = { fontSize: 'medium' as const, sx: { color: '#616161', fontSize: '1.5rem' } };
    
    // 1. Invocation -> Start Icon
    if (name.includes("invocation")) return <Start {...iconProps} />; 
    
    if (name.includes("agent")) return <SupportAgent {...iconProps} />; 
    
    // 2. LLM -> Comment Icon (Chat icon with lines inside)
    if (name.includes("llm")) return <Comment {...iconProps} />;
    
    return <Code {...iconProps} />;
  };

  // --- RENDER TREE ---
  const renderTree = (node: TraceItem) => (
    <Box key={node.span_id} sx={{ mb: 1.5, width: '100%' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ width: '100%' }}>
        <Stack direction="row" alignItems="center" spacing={1.5} sx={{ overflow: 'hidden', flexGrow: 1, mr: 2 }}>
          {getIcon(node.name)}
          <Typography variant="body2" sx={{ fontWeight: 400, color: '#424242', fontSize: '0.9rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
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
    <Box className={`right-panel-container ${isOpen ? 'open' : ''}`} sx={{ bgcolor: '#fff' }}>
      
      {/* Header */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: '#fff' }}>
         <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 1 }}>
           <Tabs 
              value={tabIndex} 
              onChange={handleTabChange} 
              sx={{ minHeight: '48px', '& .MuiTabs-indicator': { backgroundColor: '#1976d2', height: '3px' } }}
           >
             <Tab label="Events" sx={{ textTransform: 'none', fontWeight: 500, fontSize: '0.95rem', minWidth: '80px', color: '#5f6368', '&.Mui-selected': { color: '#1976d2' } }} />
             <Tab label="Trace" sx={{ textTransform: 'none', fontWeight: 500, fontSize: '0.95rem', minWidth: '80px', color: '#5f6368', '&.Mui-selected': { color: '#1976d2' } }} />
           </Tabs>
           <Stack direction="row">
              <IconButton size="small" onClick={fetchData} disabled={isLoading || !activeSessionId} sx={{ color: '#5f6368' }}>
                  <Refresh fontSize="small" />
              </IconButton>
              <IconButton size="small" onClick={onClose} sx={{ color: '#5f6368' }}>
                  <Close fontSize="small" />
              </IconButton>
           </Stack>
         </Stack>
      </Box>
      
      {/* Content */}
      <Box className="right-panel-content" sx={{ backgroundColor: '#fff', height: 'calc(100% - 49px)', overflowY: 'auto', p: 0 }}>
        {!activeSessionId ? (
           <Box sx={{ textAlign: 'center', mt: 8, color: '#5f6368' }}><Typography variant="body2">Select a session to view details.</Typography></Box>
        ) : isLoading ? (
           <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}><CircularProgress size={24} /></Box>
        ) : (
          <>
            {/* --- EVENTS TAB --- */}
            {tabIndex === 0 && (
              events.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                   <img src="/Icon.png" alt="No Data" style={{ width: '120px', opacity: 0.5, marginBottom: '16px' }} />
                   <Typography variant="body2" color="text.secondary">No events found</Typography>
                </Box>
              ) : (
                <Box sx={{ padding: '1rem'  }}>
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
                          borderTop: '1px solid #e0e0e0', 
                          borderLeft: '1px solid #e0e0e0', 
                          borderRight: '1px solid #e0e0e0', 
                          '&:before': { display: 'none' },
                          '&:last-child': { borderBottom: '1px solid #e0e0e0'},
                           padding: '0px 12px'
                        }}
                      >
                        <AccordionSummary 
                          expandIcon={<ArrowDropDown sx={{ color: '#5f6368' }} />} 
                          sx={{ 
                            px: 2, 
                            minHeight: '56px',
                            '& .MuiAccordionSummary-content': { margin: '12px 0' },
                            '&:hover': { backgroundColor: '#f8f9fa' }
                          }}
                        >
                          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ width: '100%' }}>
                             <Typography variant="body2" sx={{ fontWeight: 400, color: '#3c4043' }}>
                               {mainText.length > 50 ? mainText.substring(0, 50) + "..." : mainText}
                             </Typography>
                          </Stack>
                        </AccordionSummary>
                        
                        <AccordionDetails sx={{ px: 2, pb: 2, pt: 0 }}>
                           
                           {/* Nested Tabs: Details vs Graph */}
                           <Tabs 
                             value={evt.innerTab || 0} 
                             onChange={(e, val) => handleInnerTabChange(evt.id, val)}
                             sx={{ minHeight: '36px', mb: 2, borderBottom: '1px solid #e0e0e0' }}
                           >
                             <Tab label="Details" icon={<DataObject fontSize="small"/>} iconPosition="start" sx={{ minHeight: '36px', fontSize: '0.75rem', py: 0 }} />
                             <Tab label="Graph" icon={<AccountTree fontSize="small"/>} iconPosition="start" sx={{ minHeight: '36px', fontSize: '0.75rem', py: 0 }} />
                           </Tabs>

                           {/* 1. DETAILS TAB (JSON View) */}
                           { (evt.innerTab === 0 || evt.innerTab === undefined) && (
                             <Box sx={{ 
                                bgcolor: '#f8f9fa', 
                                p: 1.5, 
                                borderRadius: '4px', 
                                fontFamily: '"Roboto Mono", monospace', 
                                fontSize: '0.75rem', 
                                color: '#37474f', 
                                overflowX: 'auto',
                                border: '1px solid #e0e0e0'
                             }}>
                                <div style={{ marginBottom: '4px' }}><span style={{ color: '#d32f2f' }}>content</span>:</div>
                                <div style={{ paddingLeft: '16px', marginBottom: '4px' }}><span style={{ color: '#d32f2f' }}>parts</span>:</div>
                                <div style={{ paddingLeft: '32px', marginBottom: '4px' }}>0:</div>
                                <div style={{ paddingLeft: '48px', marginBottom: '4px' }}><span style={{ color: '#1976d2' }}>text</span>: "{mainText}"</div>
                                <div style={{ paddingLeft: '16px', marginBottom: '4px' }}><span style={{ color: '#1976d2' }}>role</span>: "{evt.content.role}"</div>
                                <div style={{ marginBottom: '4px' }}><span style={{ color: '#1976d2' }}>invocationId</span>: "{evt.invocationId}"</div>
                                <div style={{ marginBottom: '4px' }}><span style={{ color: '#1976d2' }}>id</span>: "{evt.id}"</div>
                                <div><span style={{ color: '#1976d2' }}>timestamp</span>: {evt.timestamp}</div>
                             </Box>
                           )}

                           {/* 2. GRAPH TAB */}
                           { evt.innerTab === 1 && (
                             <Box sx={{ mt: 1 }}>
                               {evt.graphData ? (
                                 <Box sx={{ bgcolor: '#fff', border: '1px solid #ddd', p: 1, borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                                   <pre style={{ margin: 0, fontSize: '0.7rem', color: '#555', whiteSpace: 'pre-wrap' }}>
                                     {evt.graphData.dotSrc}
                                   </pre>
                                 </Box>
                               ) : (
                                 <Typography variant="caption" color="text.secondary">Loading graph...</Typography>
                               )}
                             </Box>
                           )}

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
                <Box sx={{ p: 4, textAlign: 'center' }}>
                   <img src="/Icon.png" alt="No Data" style={{ width: '120px', opacity: 0.5, marginBottom: '16px' }} />
                   <Typography variant="body2" color="text.secondary">No traces found</Typography>
                </Box>
              ) : (
                <Box sx={{  padding: '1rem'  }}>
                  {interactions.map((interaction) => (
                    <Accordion 
                      key={interaction.traceId} 
                      disableGutters 
                      elevation={0} 
                      square
                      sx={{ 
                        borderTop: '1px solid #e0e0e0', 
                          borderLeft: '1px solid #e0e0e0', 
                          borderRight: '1px solid #e0e0e0', 
                          '&:before': { display: 'none' },
                          '&:last-child': { borderBottom: '1px solid #e0e0e0'},
                           padding: '0px 12px'
                      }}
                    >
                      <AccordionSummary 
                        expandIcon={<ArrowDropDown sx={{ color: '#5f6368' }} />} 
                        sx={{ 
                          px: 2, 
                          minHeight: '56px',
                          '& .MuiAccordionSummary-content': { margin: '12px 0' },
                          '&:hover': { backgroundColor: '#f8f9fa' }
                        }}
                      >
                        <Typography variant="body2" sx={{ fontWeight: 400, color: '#3c4043' }}>
                          {interaction.title}
                        </Typography>
                      </AccordionSummary>
                      
                      <AccordionDetails sx={{ px: 2, pb: 3, pt: 1 }}>
                        <Box sx={{ mb: 2 }}>
                           <Typography variant="body2" sx={{ color: '#444746', fontWeight: 500, fontSize: '0.95rem' }}>
                             {/* UPDATED: Displays the extracted Invocation ID */}
                             Invocation ID: <span style={{ color: '#444746' ,fontSize: '14px',fontWeight: 400,fontFamily: '"Google Sans", Roboto, Arial, sans-serif' }}>{interaction.invocationId || "N/A"}</span> 
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