import React from 'react';

const BreachDetails = ({ breach, onClose }) => {
  if (!breach) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
        <div className="mb-4">
          <h2 className="text-lg font-semibold">Breach Details</h2>
        </div>
        
        <div className="space-y-4">
          <div>
            <h3 className="font-medium text-gray-900">{breach.breach_name}</h3>
            <p className="text-sm text-gray-600">{breach.breach_description}</p>
          </div>
          
          {breach.breach_date && (
            <div>
              <span className="text-sm font-medium text-gray-700">Date: </span>
              <span className="text-sm text-gray-600">
                {new Date(breach.breach_date).toLocaleDateString()}
              </span>
            </div>
          )}
          
          <div>
            <span className="text-sm font-medium text-gray-700">Severity: </span>
            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
              breach.severity === 'high' ? 'bg-red-100 text-red-800' :
              breach.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
              'bg-green-100 text-green-800'
            }`}>
              {breach.severity}
            </span>
          </div>
          
          {breach.exposed_data && Object.keys(breach.exposed_data).length > 0 && (
            <div>
              <span className="text-sm font-medium text-gray-700">Exposed Data: </span>
              <div className="text-sm text-gray-600">
                {Object.keys(breach.exposed_data).join(', ')}
              </div>
            </div>
          )}
        </div>
        
        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default BreachDetails;
