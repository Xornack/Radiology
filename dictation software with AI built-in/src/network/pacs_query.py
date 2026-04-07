from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind

class PACSClient:
    """
    Client for querying PACS for prior studies using DICOM C-FIND.
    """
    def __init__(self, server_ip: str, server_port: int, ae_title: str):
        self.server_ip = server_ip
        self.server_port = server_port
        self.ae_title = ae_title

    def get_priors(self, patient_id: str) -> list:
        """
        Connects to PACS and fetches study-level information for the patient.
        """
        ae = AE()
        # Add presentation context for Study Root C-FIND
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

        # Create query dataset
        ds = Dataset()
        ds.QueryRetrieveLevel = 'STUDY'
        ds.PatientID = patient_id
        
        # Attributes to return
        ds.StudyInstanceUID = ''
        ds.StudyDate = ''
        ds.StudyDescription = ''
        ds.AccessionNumber = ''

        priors = []
        assoc = ae.associate(self.server_ip, self.server_port, ae_title=self.ae_title)
        
        if assoc.is_established:
            responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
            
            for (status, identifier) in responses:
                if status and status.Status == 0xFF00: # Pending
                    # Convert dataset to a simple dictionary for the UI
                    priors.append({
                        "PatientID": getattr(identifier, 'PatientID', ''),
                        "StudyDate": getattr(identifier, 'StudyDate', ''),
                        "StudyDescription": getattr(identifier, 'StudyDescription', ''),
                        "StudyInstanceUID": getattr(identifier, 'StudyInstanceUID', ''),
                        "AccessionNumber": getattr(identifier, 'AccessionNumber', '')
                    })
            assoc.release()
            
        return priors
