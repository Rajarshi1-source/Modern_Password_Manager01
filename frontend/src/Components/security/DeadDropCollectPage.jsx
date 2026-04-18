import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import CollectFragments from './CollectFragments';

const DeadDropCollectPage = () => {
  const { dropId } = useParams();
  const navigate = useNavigate();

  if (!dropId) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h2>Missing dead drop id</h2>
        <button onClick={() => navigate('/security/mesh')}>
          Back to Dead Drops
        </button>
      </div>
    );
  }

  return (
    <CollectFragments
      deadDropId={dropId}
      onSuccess={() => navigate('/security/mesh')}
      onCancel={() => navigate('/security/mesh')}
    />
  );
};

export default DeadDropCollectPage;
