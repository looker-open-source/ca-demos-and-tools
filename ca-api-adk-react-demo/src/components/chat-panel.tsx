import React, { useEffect, useRef, useState, useMemo } from 'react';
import {
  Box,
  Card,
  IconButton,
  TextField,
  Tooltip,
  Button,
  Menu,
  MenuItem,
  CircularProgress,
  LinearProgress,
  Chip,
  Avatar,
  Typography
} from '@mui/material';
import {
  SmartToy as RobotIcon,
  InsertDriveFile as FileIcon,
  Close as CloseIcon,
  Check as CheckIcon,
  Description as DescriptionIcon,
  Bolt as BoltIcon,
  Person as PersonIcon,
  AttachFile as AttachFileIcon,
  MoreVert as MoreVertIcon,
  Mic as MicIcon,
  Videocam as VideocamIcon,
  Edit as EditIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
// import DOMPurify from 'dompurify'; // Recommended for sanitizing HTML
// import ReactMarkdown from 'react-markdown'; // Recommended for markdown rendering

// --- Interfaces (Derived from usages) ---

export enum MediaType {
  IMAGE = 'image',
  AUDIO = 'audio',
  TEXT = 'text'
}

interface Attachment {
  file: File;
  url: string;
}

interface InlineData {
  mediaType: MediaType;
  data: string;
  mimeType: string;
  name: string;
  displayName?: string;
}

interface Message {
  role: 'user' | 'bot';
  eventId?: string;
  evalStatus?: number; // 0: none, 1: pass, 2: fail
  isLoading?: boolean;
  attachments?: Attachment[];
  thought?: string;
  text?: string;
  isEditing?: boolean;
  renderedContent?: string;
  executableCode?: { code: string };
  codeExecutionResult?: { outcome: string; output: string };
  inlineData?: InlineData;
  failedMetric?: boolean;
  actualInvocationToolUses?: any;
  expectedInvocationToolUses?: any;
  actualFinalResponse?: string;
  expectedFinalResponse?: string;
  evalScore?: number;
  evalThreshold?: number;
  functionCall?: { name: string };
  functionResponse?: { name: string };
}

interface EvalCase {
  // Define properties based on usage
  id: string;
}

interface ChatPanelProps {
  appName: string;
  messages: Message[];
  isChatMode?: boolean;
  evalCase?: EvalCase | null;
  isEvalEditMode?: boolean;
  isEvalCaseEditing?: boolean;
  isEditFunctionArgsEnabled?: boolean;
  userInput: string;
  userEditEvalCaseMessage: string;
  selectedFiles: { file: File; url: string }[];
  updatedSessionState?: any | null;
  eventData?: Map<string, any>;
  isAudioRecording?: boolean;
  isVideoRecording?: boolean;
  hoveredEventMessageIndices?: number[];
  
  // Services / Config (Mocked as props for React)
  isSessionLoading?: boolean;
  isMessageFileUploadEnabled?: boolean;
  isManualStateUpdateEnabled?: boolean;
  isBidiStreamingEnabled?: boolean;
  i18n?: {
    thoughtChipLabel: string;
    cancelEditingTooltip: string;
    saveEvalMessageTooltip: string;
    outcomeLabel: string;
    outputLabel: string;
    actualToolUsesLabel: string;
    expectedToolUsesLabel: string;
    actualResponseLabel: string;
    expectedResponseLabel: string;
    matchScoreLabel: string;
    thresholdLabel: string;
    evalPassLabel: string;
    evalFailLabel: string;
    editEvalMessageTooltip: string;
    deleteEvalMessageTooltip: string;
    editFunctionArgsTooltip: string;
    updatedSessionStateChipLabel: string;
    typeMessagePlaceholder: string;
    uploadFileTooltip: string;
    moreOptionsTooltip: string;
    updateStateMenuTooltip: string;
    updateStateMenuLabel: string;
    turnOffMicTooltip: string;
    useMicTooltip: string;
    turnOffCamTooltip: string;
    useCamTooltip: string;
  };

  // Events
  onUserInputChange: (value: string) => void;
  onUserEditEvalCaseMessageChange: (value: string) => void;
  onClickEvent: (index: number) => void;
  onHandleKeydown: (event: React.KeyboardEvent, message: Message) => void;
  onCancelEditMessage: (message: Message) => void;
  onSaveEditMessage: (message: Message) => void;
  onOpenViewImageDialog: (data: string) => void;
  onOpenBase64InNewTab: (data: string, mimeType: string) => void;
  onEditEvalCaseMessage: (message: Message) => void;
  onDeleteEvalCaseMessage: (message: Message, index: number) => void;
  onEditFunctionArgs: (message: Message) => void;
  onFileSelect: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveFile: (index: number) => void;
  onRemoveStateUpdate: () => void;
  onSendMessage: () => void;
  onUpdateState: () => void;
  onToggleAudioRecording: () => void;
  onToggleVideoRecording: () => void;
}

// --- Helper Components ---

// Placeholder for AudioPlayerComponent
const AudioPlayer = ({ base64data }: { base64data: string }) => (
  <audio controls src={`data:audio/wav;base64,${base64data}`} />
);

// --- Main Component ---

const ROOT_AGENT = 'root_agent';

const ChatPanel: React.FC<ChatPanelProps> = ({
  appName,
  messages,
  isChatMode = true,
  evalCase = null,
  isEvalEditMode = false,
  isEvalCaseEditing = false,
  isEditFunctionArgsEnabled = false,
  userInput,
  userEditEvalCaseMessage,
  selectedFiles,
  updatedSessionState = null,
  eventData = new Map(),
  isAudioRecording = false,
  isVideoRecording = false,
  hoveredEventMessageIndices = [],
  isSessionLoading = false,
  isMessageFileUploadEnabled = true,
  isManualStateUpdateEnabled = true,
  isBidiStreamingEnabled = true,
  i18n = {
    thoughtChipLabel: 'Thought',
    cancelEditingTooltip: 'Cancel editing',
    saveEvalMessageTooltip: 'Save message',
    outcomeLabel: 'Outcome',
    outputLabel: 'Output',
    actualToolUsesLabel: 'Actual Tool Uses',
    expectedToolUsesLabel: 'Expected Tool Uses',
    actualResponseLabel: 'Actual Response',
    expectedResponseLabel: 'Expected Response',
    matchScoreLabel: 'Match Score',
    thresholdLabel: 'Threshold',
    evalPassLabel: 'Pass',
    evalFailLabel: 'Fail',
    editEvalMessageTooltip: 'Edit message',
    deleteEvalMessageTooltip: 'Delete message',
    editFunctionArgsTooltip: 'Edit function args',
    updatedSessionStateChipLabel: 'Session State Updated',
    typeMessagePlaceholder: 'Type a message...',
    uploadFileTooltip: 'Upload file',
    moreOptionsTooltip: 'More options',
    updateStateMenuTooltip: 'Update state manually',
    updateStateMenuLabel: 'Update State',
    turnOffMicTooltip: 'Turn off microphone',
    useMicTooltip: 'Use microphone',
    turnOffCamTooltip: 'Turn off camera',
    useCamTooltip: 'Use camera',
  },
  onUserInputChange,
  onUserEditEvalCaseMessageChange,
  onClickEvent,
  onHandleKeydown,
  onCancelEditMessage,
  onSaveEditMessage,
  onOpenViewImageDialog,
  onOpenBase64InNewTab,
  onEditEvalCaseMessage,
  onDeleteEvalCaseMessage,
  onEditFunctionArgs,
  onFileSelect,
  onRemoveFile,
  onRemoveStateUpdate,
  onSendMessage,
  onUpdateState,
  onToggleAudioRecording,
  onToggleVideoRecording,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollInterrupted = useRef(false);
  const previousMessageCount = useRef(0);
  
  // State for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const openMenu = Boolean(anchorEl);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  // --- Scrolling Logic (Ported from ngOnChanges/ngAfterViewInit) ---

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleWheel = () => { scrollInterrupted.current = true; };
    const handleTouchMove = () => { scrollInterrupted.current = true; };

    container.addEventListener('wheel', handleWheel);
    container.addEventListener('touchmove', handleTouchMove);

    return () => {
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('touchmove', handleTouchMove);
    };
  }, []);

  useEffect(() => {
    if (messages.length > previousMessageCount.current) {
      const newMessages = messages.slice(previousMessageCount.current);
      if (newMessages.some(m => m.role === 'user')) {
        scrollInterrupted.current = false;
      }
      scrollToBottom();
    }
    previousMessageCount.current = messages.length;
  }, [messages]);

  const scrollToBottom = () => {
    if (!scrollInterrupted.current && scrollContainerRef.current) {
      setTimeout(() => {
        scrollContainerRef.current?.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }, 50);
    }
  };

  // --- Helpers ---

  const getAgentNameFromEvent = (index: number) => {
    const key = messages[index].eventId;
    const selectedEvent = key ? eventData.get(key) : undefined;
    return selectedEvent?.author ?? ROOT_AGENT;
  };

  // Simple string hash to color (Simulating stringToColorService)
  const stringToColor = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00ffffff).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
  };

  const getCustomIconColorStyle = (index: number) => {
    const agentName = getAgentNameFromEvent(index);
    if (agentName !== ROOT_AGENT) {
      return { color: stringToColor(agentName) };
    }
    return {};
  };

  const shouldMessageHighlighted = (index: number) => {
    return hoveredEventMessageIndices.includes(index);
  };

  const renderGooglerSearch = (content: string) => {
    // In React, we sanitize before rendering HTML
    // return { __html: DOMPurify.sanitize(content) };
  };

  // --- Render ---

  if (isSessionLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress size={50} />
      </Box>
    );
  }

  if (appName === "") return null;

  return (
    <Box display="flex" flexDirection="column" height="100%">
      {/* Messages Area */}
      <Box 
        ref={scrollContainerRef} 
        className="chat-messages" 
        flexGrow={1} 
        overflow="auto" 
        p={2}
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
      >
        <div id="videoContainer" /> {/* Placeholder for ViewChild videoContainer */}
        
        {messages.map((message, i) => (
          <Box
            key={i}
            display="flex"
            justifyContent={message.role === 'user' ? 'flex-end' : 'flex-start'}
            className={message.role === 'user' ? 'user-message' : 'bot-message'}
          >
            {/* Bot Icon */}
            {message.role === 'bot' && (
              <Tooltip title={getAgentNameFromEvent(i)}>
                <IconButton 
                  onClick={() => onClickEvent(i)}
                  disabled={!message.eventId}
                  sx={{ 
                    ...getCustomIconColorStyle(i), 
                    visibility: getAgentNameFromEvent(i) ? 'visible' : 'hidden',
                    alignSelf: 'flex-start',
                    mt: 1
                  }}
                >
                  <RobotIcon />
                </IconButton>
              </Tooltip>
            )}

            {/* Message Card or Function Buttons */}
            {!message.functionCall && !message.functionResponse && (
              <Card
                sx={{
                  maxWidth: '80%',
                  p: 2,
                  bgcolor: shouldMessageHighlighted(i) ? 'action.hover' : 'background.paper',
                  border: message.evalStatus === 2 ? '1px solid error.main' : undefined,
                  position: 'relative'
                }}
              >
                {message.isLoading && <LinearProgress sx={{ mb: 1 }} />}

                {/* Attachments */}
                {message.attachments && (
                  <Box display="flex" flexWrap="wrap" gap={1} mb={1}>
                    {message.attachments.map((file, idx) => (
                      <Box key={idx} display="flex" alignItems="center" gap={0.5}>
                        {file.file.type.startsWith('image/') ? (
                          <img 
                            src={file.url} 
                            alt="attachment" 
                            style={{ maxHeight: 100, borderRadius: 4 }} 
                          />
                        ) : (
                          <>
                            <FileIcon fontSize="small" />
                            {file.url ? (
                              <a href={file.url} download>{file.file.name}</a>
                            ) : (
                              <Typography variant="body2">{file.file.name}</Typography>
                            )}
                          </>
                        )}
                      </Box>
                    ))}
                  </Box>
                )}

                {/* Content */}
                <Box>
                  {message.thought && (
                    <Chip label={i18n.thoughtChipLabel} size="small" sx={{ mb: 1 }} />
                  )}
                  
                  {message.text && (
                    <Box>
                      {/* {message.isEditing ? (
                        <Box className="edit-message-container">
                          <TextField
                            fullWidth
                            multiline
                            minRows={4}
                            value={userEditEvalCaseMessage}
                            onChange={(e) => onUserEditEvalCaseMessageChange(e.target.value)}
                            onKeyDown={(e) => onHandleKeydown(e, message)}
                          />
                          <Box display="flex" justifyContent="flex-end" mt={1}>
                            <Tooltip title={i18n.cancelEditingTooltip}>
                              <IconButton onClick={() => onCancelEditMessage(message)}>
                                <CloseIcon />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title={i18n.saveEvalMessageTooltip}>
                              <IconButton onClick={() => onSaveEditMessage(message)}>
                                <CheckIcon />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </Box>
                      ) : (
                         <ReactMarkdown>{message.text}</ReactMarkdown>
                      )} */}
                    </Box>
                  )}

                  {/* {message.renderedContent && (
                     <div dangerouslySetInnerHTML={renderGooglerSearch(message.renderedContent)} />
                  )} */}
                </Box>

                {/* Executable Code */}
                {message.executableCode && (
                  <Box component="pre" bgcolor="grey.100" p={1} borderRadius={1} mt={1}>
                    <code>{message.executableCode.code}</code>
                  </Box>
                )}

                {/* Execution Result */}
                {message.codeExecutionResult && (
                  <Box mt={1}>
                    <Typography variant="body2">
                      {i18n.outcomeLabel}: {message.codeExecutionResult.outcome}
                    </Typography>
                    <Typography variant="body2">
                      {i18n.outputLabel}: {message.codeExecutionResult.output}
                    </Typography>
                  </Box>
                )}

                {/* Inline Data (Images, Audio, Text Artifacts) */}
                {message.inlineData && message.role === 'bot' && (
                  <Box mt={1}>
                    {(() => {
                      switch (message.inlineData.mediaType) {
                        case MediaType.IMAGE:
                          return (
                            <img
                              src={message.inlineData.data}
                              alt="generated"
                              style={{ maxWidth: '100%', cursor: 'pointer' }}
                              onClick={() => onOpenViewImageDialog(message.inlineData!.data)}
                            />
                          );
                        case MediaType.AUDIO:
                          return <AudioPlayer base64data={message.inlineData.data} />;
                        case MediaType.TEXT:
                        default:
                          return (
                            <Button
                              startIcon={message.inlineData.mediaType === MediaType.TEXT ? <DescriptionIcon /> : undefined}
                              onClick={() => onOpenBase64InNewTab(message.inlineData!.data, message.inlineData!.mimeType)}
                            >
                              {message.inlineData.name || message.inlineData.displayName}
                            </Button>
                          );
                      }
                    })()}
                  </Box>
                )}

                {/* Eval Compare (Fail state) */}
                {message.failedMetric && message.evalStatus === 2 && (
                  <Box className="eval-compare-container" mt={2}>
                    <Box display="flex" gap={2}>
                      {message.actualInvocationToolUses ? (
                         <>
                           <Box flex={1}>
                             <Typography variant="subtitle2">{i18n.actualToolUsesLabel}</Typography>
                             <ReactJson src={message.actualInvocationToolUses} collapsed={1} />
                           </Box>
                           <Box flex={1}>
                             <Typography variant="subtitle2">{i18n.expectedToolUsesLabel}</Typography>
                             <ReactJson src={message.expectedInvocationToolUses} collapsed={1} />
                           </Box>
                         </>
                      ) : message.actualFinalResponse ? (
                        <>
                           <Box flex={1}>
                             <Typography variant="subtitle2">{i18n.actualResponseLabel}</Typography>
                             <Typography variant="body2">{message.actualFinalResponse}</Typography>
                           </Box>
                           <Box flex={1}>
                             <Typography variant="subtitle2">{i18n.expectedResponseLabel}</Typography>
                             <Typography variant="body2">{message.expectedFinalResponse}</Typography>
                           </Box>
                        </>
                      ) : null}
                    </Box>
                    {message.evalScore !== undefined && message.evalThreshold !== undefined && (
                      <Box mt={1}>
                         <Typography variant="caption" display="block">
                           {i18n.matchScoreLabel}: {message.evalScore}
                         </Typography>
                         <Typography variant="caption" display="block">
                           {i18n.thresholdLabel}: {message.evalThreshold}
                         </Typography>
                      </Box>
                    )}
                  </Box>
                )}

                {/* User Message Inline Data */}
                 {message.role === 'user' && message.inlineData && (
                    <Box mt={1}>
                      {message.inlineData.mimeType.startsWith('image/') ? (
                         <img 
                           src={message.inlineData.data} 
                           alt="user upload" 
                           style={{ maxHeight: 150, cursor: 'pointer' }}
                           onClick={() => onOpenViewImageDialog(message.inlineData!.data)}
                         />
                      ) : (
                        <Box display="flex" alignItems="center" gap={1}>
                           <FileIcon />
                           <a href={message.inlineData.data} download>{message.inlineData.displayName}</a>
                        </Box>
                      )}
                    </Box>
                 )}
              </Card>
            )}

            {/* Function Call / Response Buttons */}
            {(message.functionCall || message.functionResponse) && (
              <Button
                variant="outlined"
                onClick={() => onClickEvent(i)}
                sx={{
                  bgcolor: shouldMessageHighlighted(i) ? 'action.hover' : undefined,
                  textTransform: 'none'
                }}
                startIcon={message.functionCall ? <BoltIcon /> : <CheckIcon />}
              >
                {message.functionCall?.name || message.functionResponse?.name}
              </Button>
            )}

            {/* Eval Status Icon */}
            {message.evalStatus && (
               <Box ml={1} display="flex" alignItems="center" color={message.evalStatus === 1 ? 'success.main' : 'error.main'}>
                  {message.evalStatus === 1 ? <CheckIcon fontSize="small" /> : <CloseIcon fontSize="small" />}
                  <Typography variant="caption">
                    {message.evalStatus === 1 ? i18n.evalPassLabel : i18n.evalFailLabel}
                  </Typography>
               </Box>
            )}

            {/* Edit Controls (Eval Edit Mode) */}
            {evalCase && message.role === 'bot' && isEvalEditMode && !isEvalCaseEditing && (
              <Box display="flex" flexDirection="column">
                 {message.text && (
                   <>
                     <Tooltip title={i18n.editEvalMessageTooltip}>
                       <IconButton size="small" onClick={() => onEditEvalCaseMessage(message)}>
                         <EditIcon fontSize="small" />
                       </IconButton>
                     </Tooltip>
                     <Tooltip title={i18n.deleteEvalMessageTooltip}>
                       <IconButton size="small" onClick={() => onDeleteEvalCaseMessage(message, i)}>
                         <DeleteIcon fontSize="small" />
                       </IconButton>
                     </Tooltip>
                   </>
                 )}
                 {isEditFunctionArgsEnabled && message.functionCall && (
                   <Tooltip title={i18n.editFunctionArgsTooltip}>
                     <IconButton size="small" onClick={() => onEditFunctionArgs(message)}>
                       <EditIcon fontSize="small" />
                     </IconButton>
                   </Tooltip>
                 )}
              </Box>
            )}

            {/* User Icon */}
            {message.role === 'user' && (
              <Avatar sx={{ width: 32, height: 32, ml: 1, bgcolor: 'primary.main' }}>
                <PersonIcon fontSize="small" />
              </Avatar>
            )}
          </Box>
        ))}
      </Box>

      {/* Input Area */}
      {isChatMode && !isSessionLoading && (
        <Box p={2} borderTop={1} borderColor="divider">
          <input
            type="file"
            multiple
            hidden
            ref={fileInputRef}
            onChange={onFileSelect}
          />
          
          <Box display="flex" alignItems="flex-end" gap={1}>
             {/* Preview Area (Files/Updates) */}
             {((selectedFiles.length > 0 && appName !== "") || updatedSessionState) && (
               <Box width="100%" mb={1}>
                  {selectedFiles.map((file, i) => (
                    <Chip
                      key={i}
                      label={file.file.name}
                      onDelete={() => onRemoveFile(i)}
                      avatar={file.file.type.startsWith('image/') ? <Avatar src={file.url} /> : <FileIcon />}
                      sx={{ mr: 1, mb: 1 }}
                    />
                  ))}
                  {updatedSessionState && (
                    <Chip
                      label={i18n.updatedSessionStateChipLabel}
                      onDelete={onRemoveStateUpdate}
                      color="info"
                    />
                  )}
               </Box>
             )}

             <TextField
               fullWidth
               multiline
               maxRows={10}
               placeholder={i18n.typeMessagePlaceholder}
               value={userInput}
               onChange={(e) => onUserInputChange(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === 'Enter' && !e.shiftKey) {
                   e.preventDefault();
                   onSendMessage();
                 }
               }}
               InputProps={{
                 endAdornment: (
                   <Box display="flex">
                      <Tooltip title={i18n.uploadFileTooltip}>
                        <span>
                          <IconButton 
                            onClick={() => fileInputRef.current?.click()}
                            disabled={!isMessageFileUploadEnabled}
                          >
                            <AttachFileIcon />
                          </IconButton>
                        </span>
                      </Tooltip>
                      
                      <Tooltip title={i18n.moreOptionsTooltip}>
                        <span>
                          <IconButton 
                            onClick={handleMenuClick}
                            disabled={!isManualStateUpdateEnabled}
                          >
                            <MoreVertIcon />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Menu
                        anchorEl={anchorEl}
                        open={openMenu}
                        onClose={handleMenuClose}
                      >
                        <MenuItem onClick={() => { onUpdateState(); handleMenuClose(); }}>
                           {i18n.updateStateMenuLabel}
                        </MenuItem>
                      </Menu>

                      <Tooltip title={isAudioRecording ? i18n.turnOffMicTooltip : i18n.useMicTooltip}>
                         <span>
                           <IconButton 
                             onClick={onToggleAudioRecording}
                             color={isAudioRecording ? 'error' : 'default'}
                             disabled={!isBidiStreamingEnabled}
                           >
                             <MicIcon />
                           </IconButton>
                         </span>
                      </Tooltip>

                      <Tooltip title={isVideoRecording ? i18n.turnOffCamTooltip : i18n.useCamTooltip}>
                         <span>
                            <IconButton
                              onClick={onToggleVideoRecording}
                              color={isVideoRecording ? 'error' : 'default'}
                              disabled={!isBidiStreamingEnabled}
                            >
                              <VideocamIcon />
                            </IconButton>
                         </span>
                      </Tooltip>
                   </Box>
                 )
               }}
             />
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default ChatPanel;