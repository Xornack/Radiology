import pytest
import threading
from pydicom.dataset import Dataset
from pynetdicom import AE, evt
from src.network.pacs_query import PACSClient

# --- Mock SCP Setup ---
def handle_find(event):
    """Handle a C-FIND request event."""
    # Simulation: Return one study for any request
    ds = Dataset()
    ds.PatientID = event.identifier.PatientID
    ds.StudyDate = "20230101"
    ds.StudyDescription = "MOCK STUDY"
    ds.StudyInstanceUID = "1.2.3.4"
    ds.QueryRetrieveLevel = "STUDY"
    
    # 0xFF00 is 'Pending' status, meaning more results or this is a result
    yield (0xFF00, ds)

@pytest.fixture
def mock_pacs():
    """Starts a local DICOM SCP for testing."""
    ae = AE()
    ae.add_supported_context('1.2.840.10008.5.1.4.1.2.2.1') # Study Root FIND
    
    handlers = [(evt.EVT_C_FIND, handle_find)]
    scp = ae.start_server(('127.0.0.1', 11112), block=False, evt_handlers=handlers)
    yield scp
    scp.shutdown()

# --- The Test ---
def test_get_priors_integration(mock_pacs):
    """
    Ensures PACSClient correctly connects to a DICOM server, 
    sends a C-FIND, and returns parsed study data.
    """
    client = PACSClient(server_ip='127.0.0.1', server_port=11112, ae_title='ANY-SCP')
    priors = client.get_priors(patient_id="12345")
    
    assert len(priors) > 0
    assert priors[0]['PatientID'] == "12345"
    assert priors[0]['StudyDate'] == "20230101"
    assert priors[0]['StudyDescription'] == "MOCK STUDY"
