type Props = {
  onStart: () => void;
  onSimulateFirstVisit: () => void;
};

export function TourLauncher({ onStart, onSimulateFirstVisit }: Props) {
  return (
    <div className="tour-launcher" data-tour="tour-launcher">
      <button type="button" className="tour-launcher-main" onClick={onStart}>
        Tour
      </button>
      <button type="button" className="tour-launcher-secondary" onClick={onSimulateFirstVisit}>
        Simulate first visit
      </button>
    </div>
  );
}
