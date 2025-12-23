import React, { useEffect, useState } from 'react';
import {Box, Typography, Stack, IconButton, CircularProgress,Accordion, AccordionSummary, AccordionDetails, Tabs, Tab, Divider} from '@mui/material';
import {Close, Refresh,ArrowDropDown,Input,SupportAgent,ChatBubbleOutline,Code} from '@mui/icons-material';
import { useSession } from '../context/SessionContext';
import { apiClient } from '../services/clientService';
import '../App.css'; 

interface RightPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

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

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabIndex(newValue);
  };

  const fetchData = async () => {
    if (!activeSessionId || !selectedAgentId) return;
    setIsLoading(true);
    
    try {
      if (tabIndex === 0) {

        const response: SessionResponse = await apiClient.get(`/apps/${selectedAgentId}/users/user/sessions/${activeSessionId}`);
        if (response && Array.isArray(response.events)) {
          const filteredEvents = response.events.filter(evt => evt.content.role !== 'user').sort((a, b) => b.timestamp - a.timestamp);
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

      return { traceId, title, rootSpans };
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
    const iconProps = { sx: { color: '#616161', fontSize: '1.3rem' } };
    if (name.includes("invocation")) return <Input {...iconProps} />; 
    if (name.includes("agent")) return <SupportAgent {...iconProps} />; 
    if (name.includes("llm")) return <ChatBubbleOutline {...iconProps} />;
    return <Code {...iconProps} />;
  };

  const renderTree = (node: TraceItem) => (
    <Box key={node.span_id} sx={{ mb: 1.5, width: '100%' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ width: '100%' }}>
        
        <Stack direction="row" alignItems="center" spacing={1.5} sx={{ overflow: 'hidden', flexGrow: 1, mr: 2 }}>
          {getIcon(node.name)}
          <Typography variant="body2" sx={{fontWeight: 400,color: '#424242',fontSize: '0.9rem',whiteSpace: 'nowrap',overflow: 'hidden',textOverflow: 'ellipsis'}}>
            {node.name}
          </Typography>
        </Stack>
        
        <Box sx={{bgcolor: '#e3f2fd',color: '#1967d2',borderRadius: '4px',px: 1.5,py: 0.5,fontSize: '0.8rem', fontWeight: 500, minWidth: '90px',textAlign: 'left',flexShrink: 0 }}>
          {calculateDuration(node.start_time, node.end_time)}
        </Box>
      </Stack>


      {node.children && node.children.length > 0 && (
        <Box sx={{pl: 3.5,mt: 1.5,display: 'flex',flexDirection: 'column',gap: 1.5 }}>
          {node.children.map(child => renderTree(child))}
        </Box>
      )}
    </Box>
  );

  return (
    <Box className={`right-panel-container ${isOpen ? 'open' : ''}`} sx={{ bgcolor: '#fff' }}>
      
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: '#fff' }}>
         <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 1 }}>
           <Tabs value={tabIndex} onChange={handleTabChange} sx={{ minHeight: '48px', '& .MuiTabs-indicator': { backgroundColor: '#1976d2', height: '3px' } }}>
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
      
      <Box className="right-panel-content" sx={{ backgroundColor: '#fff', height: 'calc(100% - 49px)', overflowY: 'auto', p: 0 }}>
        {!activeSessionId ? (
           <Box sx={{ textAlign: 'center', mt: 8, color: '#5f6368' }}><Typography variant="body2">Select a session to view details.</Typography></Box>) 
           : isLoading ? (<Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}><CircularProgress size={24} /></Box>) 
           : (
           <>
           {tabIndex === 0 && (
              events.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                   <img src="/Icon.png" alt="No Data" style={{ width: '120px', opacity: 0.5, marginBottom: '16px' }} />
                   <Typography variant="body2" color="text.secondary">No events found</Typography>
                </Box>
              ) : (
                <Box sx={{ padding: '1rem' }}>
                  {events.map((evt) => {
                    const mainText = evt.content.parts?.[0]?.text || "No content";
                    return (
                      <Accordion key={evt.id} disableGutters elevation={0} square
                        sx={{ 
                          borderTop: '1px solid #e0e0e0', 
                          borderLeft: '1px solid #e0e0e0', 
                          borderRight: '1px solid #e0e0e0', 
                          '&:before': { display: 'none' },
                          '&:last-child': { borderBottom: '1px solid #e0e0e0' },
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
                             {mainText.length > 50 ? mainText.substring(0, 50) + "..." : mainText}
                          </Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ px: 2, pb: 2, pt: 0 }}>
                           <Typography variant="body2" sx={{ color: '#3c4043', whiteSpace: 'pre-wrap', fontSize: '0.875rem', mb: 2 }}>
                             {mainText}
                           </Typography>
                           <Divider sx={{ my: 1 }} />
                           <Stack spacing={0.5} mt={1}>
                             <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                               <strong>ID:</strong> {evt.id}
                             </Typography>
                             <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                               <strong>Time:</strong> {formatTimestamp(evt.timestamp)}
                             </Typography>
                             {evt.invocationId && (
                               <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                                 <strong>Invocation ID:</strong> {evt.invocationId}
                               </Typography>
                             )}
                           </Stack>
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
                <Box sx={{ borderTop: '1px solid #e0e0e0' }}>
                  {interactions.map((interaction) => (
                    <Accordion 
                      key={interaction.traceId} 
                      disableGutters 
                      elevation={0} 
                      square
                      sx={{ 
                        borderBottom: '1px solid #e0e0e0', 
                        '&:before': { display: 'none' },
                        '&:last-child': { borderBottom: 'none' }
                      }}
                    >
                      {/* Arrow on Right (Default) */}
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
                           <Typography variant="body2" sx={{ color: '#424242', fontWeight: 500, fontSize: '0.95rem' }}>
                             Invocation ID: {interaction.rootSpans[0]?.attributes["gcp.vertex.agent.invocation_id"] || "N/A"}
                           </Typography>
                        </Box>
                        
                        {/* Render Tree with new styling */}
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