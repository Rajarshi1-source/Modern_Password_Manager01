/**
 * Challenge Card Component
 * 
 * Generic card wrapper for displaying challenges
 */

import React from 'react';
import styled from 'styled-components';

const Card = styled.div`
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  padding: 32px;
  margin-bottom: 24px;
  
  ${props => props.highlighted && `
    border: 2px solid #667eea;
    box-shadow: 0 8px 30px rgba(102, 126, 234, 0.2);
  `}
`;

const CardHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid #f0f0f0;
`;

const CardTitle = styled.h3`
  margin: 0;
  color: #333;
  font-size: 20px;
  font-weight: 600;
`;

const CardBadge = styled.span`
  background: ${props => props.color || '#667eea'};
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
`;

const CardContent = styled.div`
  color: #666;
  line-height: 1.6;
`;

const ChallengeCard = ({ 
  title, 
  badge, 
  badgeColor, 
  highlighted, 
  children 
}) => {
  return (
    <Card highlighted={highlighted}>
      {(title || badge) && (
        <CardHeader>
          {title && <CardTitle>{title}</CardTitle>}
          {badge && <CardBadge color={badgeColor}>{badge}</CardBadge>}
        </CardHeader>
      )}
      <CardContent>
        {children}
      </CardContent>
    </Card>
  );
};

export default ChallengeCard;

