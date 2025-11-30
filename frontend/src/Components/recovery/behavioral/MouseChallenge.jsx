/**
 * Mouse Challenge Component
 * 
 * Presents mouse biometric challenges during behavioral recovery
 * Captures movement patterns, click timing, and navigation behavior
 */

import React, { useState, useEffect, useRef } from 'react';
import styled from 'styled-components';
import { FaMouse, FaCheckCircle, FaArrowRight } from 'react-icons/fa';
import { MouseBiometrics } from '../../../services/behavioralCapture/MouseBiometrics';

const ChallengeContainer = styled.div`
  background: white;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
`;

const ChallengeHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  
  svg {
    font-size: 32px;
    color: #667eea;
  }
  
  h2 {
    margin: 0;
    color: #333;
    font-size: 24px;
  }
`;

const Instruction = styled.p`
  color: #666;
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 24px;
`;

const InteractionArea = styled.div`
  background: #f9f9f9;
  border: 2px dashed #ccc;
  border-radius: 12px;
  padding: 40px;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  margin-bottom: 24px;
  position: relative;
`;

const TargetButton = styled.button`
  padding: 16px 32px;
  background: ${props => props.clicked ? '#4caf50' : '#667eea'};
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  position: ${props => props.absolute ? 'absolute' : 'relative'};
  left: ${props => props.x || 'auto'}px;
  top: ${props => props.y || 'auto'}px;
  
  &:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  }
  
  ${props => props.clicked && `
    &::after {
      content: '✓';
      margin-left: 8px;
    }
  `}
`;

const DragItem = styled.div`
  padding: 12px 24px;
  background: white;
  border: 2px solid #667eea;
  border-radius: 8px;
  cursor: move;
  user-select: none;
  transition: transform 0.2s;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
  }
  
  &[draggable="true"] {
    opacity: ${props => props.isDragging ? 0.5 : 1};
  }
`;

const DropZone = styled.div`
  min-height: 60px;
  background: ${props => props.isOver ? '#e3f2fd' : '#f5f5f5'};
  border: 2px dashed ${props => props.isOver ? '#667eea' : '#ccc'};
  border-radius: 8px;
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  transition: all 0.3s;
`;

const Stats = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin: 20px 0;
`;

const StatItem = styled.div`
  background: #f9f9f9;
  padding: 12px;
  border-radius: 8px;
  text-align: center;
  
  .label {
    font-size: 11px;
    color: #999;
    margin-bottom: 4px;
  }
  
  .value {
    font-size: 18px;
    font-weight: 600;
    color: #333;
  }
`;

const Button = styled.button`
  padding: 14px 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
  transition: transform 0.2s;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const MouseChallenge = ({ challenge, onComplete, challengeNumber, totalChallenges }) => {
  const [clickedTargets, setClickedTargets] = useState(new Set());
  const [draggedItems, setDraggedItems] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [stats, setStats] = useState({
    clicks: 0,
    movements: 0,
    avgVelocity: 0,
    distance: 0
  });
  
  const mouseBiometricsRef = useRef(null);
  const startTimeRef = useRef(null);
  
  // Initialize mouse biometrics capture
  useEffect(() => {
    mouseBiometricsRef.current = new MouseBiometrics();
    mouseBiometricsRef.current.attach();
    startTimeRef.current = Date.now();
    
    // Update stats periodically
    const statsInterval = setInterval(() => {
      if (mouseBiometricsRef.current) {
        const mouseStats = mouseBiometricsRef.current.stats;
        setStats({
          clicks: mouseStats.clicks.length,
          movements: mouseStats.movements.length,
          avgVelocity: mouseStats.velocities.length > 0
            ? Math.round(mouseBiometricsRef.current._mean(mouseStats.velocities) * 1000)
            : 0,
          distance: Math.round(mouseStats.totalDistance)
        });
      }
    }, 500);
    
    return () => {
      clearInterval(statsInterval);
      if (mouseBiometricsRef.current) {
        mouseBiometricsRef.current.detach();
      }
    };
  }, [challenge]);
  
  const taskData = challenge?.challenge_data?.task_data || {};
  const taskType = taskData.task || 'click';
  
  // Handle target click
  const handleTargetClick = (index) => {
    const newClicked = new Set(clickedTargets);
    newClicked.add(index);
    setClickedTargets(newClicked);
    
    // Check if all targets clicked
    const totalTargets = taskData.targets?.length || 3;
    if (newClicked.size >= totalTargets) {
      setIsComplete(true);
    }
  };
  
  // Handle drag start
  const handleDragStart = (e, item) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', item);
  };
  
  // Handle drop
  const handleDrop = (e) => {
    e.preventDefault();
    const item = e.dataTransfer.getData('text/plain');
    
    if (!draggedItems.includes(item)) {
      setDraggedItems([...draggedItems, item]);
    }
    
    // Check if all items dragged
    const totalItems = taskData.items?.length || 3;
    if (draggedItems.length + 1 >= totalItems) {
      setIsComplete(true);
    }
  };
  
  const handleDragOver = (e) => {
    e.preventDefault();
  };
  
  const handleSubmit = async () => {
    if (!isComplete || !mouseBiometricsRef.current) return;
    
    // Collect behavioral data
    const behavioralData = await mouseBiometricsRef.current.getFeatures();
    
    const challengeResponse = {
      ...behavioralData,
      challenge_id: challenge.challenge_id,
      challenge_type: 'mouse',
      completed: true,
      time_taken: Date.now() - startTimeRef.current,
      stats: stats,
      task_completed: {
        type: taskType,
        targets_clicked: clickedTargets.size,
        items_dragged: draggedItems.length
      }
    };
    
    // Reset
    mouseBiometricsRef.current.reset();
    setClickedTargets(new Set());
    setDraggedItems([]);
    setIsComplete(false);
    
    if (onComplete) {
      onComplete(challengeResponse);
    }
  };
  
  // Render click task
  const renderClickTask = () => {
    const targets = taskData.targets || [
      { label: 'Target 1', x: 100, y: 50 },
      { label: 'Target 2', x: 300, y: 100 },
      { label: 'Target 3', x: 200, y: 200 }
    ];
    
    return (
      <InteractionArea>
        <p style={{ position: 'absolute', top: '12px', color: '#999', fontSize: '14px' }}>
          Click the targets in order
        </p>
        {targets.map((target, index) => (
          <TargetButton
            key={index}
            absolute={true}
            x={target.x}
            y={target.y}
            clicked={clickedTargets.has(index)}
            onClick={() => handleTargetClick(index)}
          >
            {target.label}
          </TargetButton>
        ))}
      </InteractionArea>
    );
  };
  
  // Render drag task
  const renderDragTask = () => {
    const items = taskData.items || ['Item 1', 'Item 2', 'Item 3'];
    
    return (
      <>
        <div style={{ marginBottom: '16px' }}>
          {items.map((item, index) => (
            <DragItem
              key={index}
              draggable
              onDragStart={(e) => handleDragStart(e, item)}
              style={{ display: 'inline-block', margin: '8px' }}
            >
              {item}
            </DragItem>
          ))}
        </div>
        <DropZone
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {draggedItems.length === 0 ? (
            <span style={{ color: '#999' }}>Drag items here</span>
          ) : (
            draggedItems.map((item, index) => (
              <span key={index} style={{ 
                background: '#4caf50', 
                color: 'white', 
                padding: '4px 12px', 
                borderRadius: '4px',
                margin: '4px'
              }}>
                {item}
              </span>
            ))
          )}
        </DropZone>
      </>
    );
  };
  
  return (
    <ChallengeContainer>
      <ChallengeHeader>
        <FaMouse />
        <div>
          <h2>Mouse Challenge {challengeNumber}/{totalChallenges}</h2>
          <p style={{ margin: 0, color: '#999', fontSize: '14px' }}>
            Complete the mouse interaction tasks naturally
          </p>
        </div>
      </ChallengeHeader>
      
      <Instruction>
        {challenge?.challenge_data?.instruction || 'Complete the mouse interaction task below'}
      </Instruction>
      
      {taskType === 'drag' ? renderDragTask() : renderClickTask()}
      
      <Stats>
        <StatItem>
          <div className="label">Clicks</div>
          <div className="value">{stats.clicks}</div>
        </StatItem>
        <StatItem>
          <div className="label">Movements</div>
          <div className="value">{stats.movements}</div>
        </StatItem>
        <StatItem>
          <div className="label">Avg Speed</div>
          <div className="value">{stats.avgVelocity}</div>
        </StatItem>
        <StatItem>
          <div className="label">Distance</div>
          <div className="value">{stats.distance}px</div>
        </StatItem>
      </Stats>
      
      {isComplete && (
        <div style={{ 
          background: '#e8f5e9', 
          color: '#2e7d32', 
          padding: '12px', 
          borderRadius: '8px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <FaCheckCircle />
          <span>Task completed successfully!</span>
        </div>
      )}
      
      <Button onClick={handleSubmit} disabled={!isComplete}>
        {isComplete ? (
          <>
            Submit & Continue
            <FaArrowRight />
          </>
        ) : (
          'Complete task to continue'
        )}
      </Button>
    </ChallengeContainer>
  );
};

export default MouseChallenge;

