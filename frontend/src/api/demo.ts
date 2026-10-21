import client from './client';

export type ScenarioName = 'green' | 'yellow' | 'red' | 'overdue';

export async function switchScenario(name: ScenarioName): Promise<void> {
  await client.post(`/api/v1/demo/scenario/${name}`);
}

export async function getActiveScenario(): Promise<ScenarioName> {
  const { data } = await client.get<{ active_scenario: ScenarioName }>('/api/v1/demo/scenario');
  return data.active_scenario;
}
