from loguru import logger
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind


class PACSClient:
    """
    Client for querying PACS for prior studies using DICOM C-FIND.
    """
    def __init__(
        self,
        server_ip: str,
        server_port: int,
        ae_title: str,
        network_timeout: int = 10,
        acse_timeout: int = 10,
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.ae_title = ae_title
        self.network_timeout = network_timeout
        self.acse_timeout = acse_timeout

    def get_priors(self, patient_id: str) -> list:
        """
        Connects to PACS and fetches study-level information for the patient.
        Returns an empty list if association fails, the query fails, or no
        priors match. Timeouts bound hang time when the PACS is unreachable.
        """
        ae = AE()
        ae.acse_timeout = self.acse_timeout
        ae.network_timeout = self.network_timeout
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

        ds = Dataset()
        ds.QueryRetrieveLevel = 'STUDY'
        ds.PatientID = patient_id
        ds.StudyInstanceUID = ''
        ds.StudyDate = ''
        ds.StudyDescription = ''
        ds.AccessionNumber = ''

        priors: list = []
        assoc = None
        try:
            assoc = ae.associate(
                self.server_ip, self.server_port, ae_title=self.ae_title
            )
            if not assoc.is_established:
                logger.error(
                    f"PACS association failed to {self.server_ip}:{self.server_port} "
                    f"(AE: {self.ae_title})"
                )
                return priors

            responses = assoc.send_c_find(
                ds, StudyRootQueryRetrieveInformationModelFind
            )
            for status, identifier in responses:
                if status and status.Status == 0xFF00 and identifier is not None:
                    priors.append({
                        "PatientID": getattr(identifier, 'PatientID', ''),
                        "StudyDate": getattr(identifier, 'StudyDate', ''),
                        "StudyDescription": getattr(
                            identifier, 'StudyDescription', ''
                        ),
                        "StudyInstanceUID": getattr(
                            identifier, 'StudyInstanceUID', ''
                        ),
                        "AccessionNumber": getattr(
                            identifier, 'AccessionNumber', ''
                        ),
                    })
        except Exception as e:
            logger.error(f"PACS C-FIND failed: {e}")
        finally:
            if assoc is not None and assoc.is_established:
                assoc.release()

        return priors
