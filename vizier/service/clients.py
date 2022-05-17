"""OSS Vizier client."""

import copy
from typing import Any, Collection, Mapping, Optional, Type

from absl import flags
import attr
from vizier._src.pyvizier.client import client_abc
from vizier.service import pyvizier as vz
from vizier.service import vizier_client

SERVICE_ENDPOINT = flags.DEFINE_string(
    'service_endpoint', '',
    'Address of VizierService for creation of gRPC stub, e.g. "localhost:8998".'
)
FLAGS = flags.FLAGS

_UNUSED_CLIENT_ID = 'Unused client id.'


@attr.define
class Study(client_abc.StudyInterface):
  """Responsible for study-level operations."""

  _client: vizier_client.VizierClient = attr.field()

  @classmethod
  def from_config(cls, study_config: vz.StudyConfig, service_endpoint: str,
                  owner_id: str, study_display_name: str) -> 'Study':
    pass

  def suggest(self,
              *,
              count: Optional[int] = None,
              client_id: str) -> Collection['Trial']:
    self._client.get_suggestions(client_id_override=client_id)

  def delete(self) -> None:
    self._client.delete_study(self._client.study_name)

  def trials(
      self,
      trial_filter: Optional[vz.TrialFilter] = None) -> Collection['Trial']:
    all_trials = self._client.list_trials()
    for t in filter(trial_filter, all_trials):
      return Trial(self._client, t.id)

  def get_trial(self, uid: int) -> 'Trial':
    return Trial(self._client, uid)

  def optimal_trials(self) -> Collection['Trial']:
    trials = self._client.list_optimal_trials()
    for t in trials:
      return Trial(self._client, t.id)

  def materialize_study_config(self) -> vz.StudyConfig:
    return self._client.get_study_config()

  @classmethod
  def from_uid(cls: Type['Study'], uid: str) -> 'Study':
    return Study(
        vizier_client.VizierClient(SERVICE_ENDPOINT.value, uid,
                                   _UNUSED_CLIENT_ID))


@attr.define
class Trial(client_abc.TrialInterface):
  """Trial class."""

  _client: vizier_client.VizierClient = attr.field()
  _uid: int = attr.field()
  _study_config: vz.StudyConfig = attr.field(default=None)
  _trial: vz.Trial = attr.field(default=None)

  @property
  def refresh(self) -> None:
    self._trial = self._client.get_trial(self._uid)
    self._study_config = self._client.get_study_config()

  @property
  def uid(self) -> int:
    return self._uid

  @property
  def parameters(self) -> Mapping[str, Any]:
    return self._study_config.trial_parameters(
        vz.TrialConverter.to_proto(self._trial))

  @property
  def status(self) -> vz.TrialStatus:
    return self._trial.status

  def delete(self) -> None:
    self._client.delete_trial(self._uid)

  def complete(
      self,
      measurement: Optional[vz.Measurement] = None,
      *,
      infeasible_reason: Optional[str] = None) -> Optional[vz.Measurement]:
    self._trial = self._client.complete_trial(self._uid, measurement,
                                              infeasible_reason)

  def should_stop(self) -> bool:
    return self._client.should_trial_stop(self._uid)

  def add_measurement(self, measurement: vz.Measurement) -> None:
    self._client.report_intermediate_objective_value(
        measurement.steps, measurement.elapsed_secs,
        {k: v.value for k, v in measurement.metrics.items()})
    self._trial.measurements.append(measurement)

  def materialize(self, *, include_all_measurements: bool = True) -> vz.Trial:
    return copy.deepcopy(self._trial)
