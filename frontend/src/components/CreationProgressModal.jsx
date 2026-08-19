export default function CreationProgressModal({ label, error, onDismissError }) {
  return (
    <div className="modal-overlay">
      <div className={`progress-modal${error ? " progress-error" : ""}`}>
        <div className="progress-spinner" />
        <p>{error || label}</p>
        {error && (
          <button type="button" className="link-button" onClick={onDismissError}>
            Close
          </button>
        )}
      </div>
    </div>
  );
}
