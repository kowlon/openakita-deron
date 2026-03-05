import { FC } from 'react'
import type { Scenario } from '../../types/scenario'

interface ScenarioListProps {
  scenarios: Scenario[]
  onStart?: (scenarioId: string) => void
  onSelect?: (scenario: Scenario) => void
  selectedId?: string
  filter?: string
}

const categoryColors: Record<string, string> = {
  development: 'bg-purple-100 text-purple-700',
  productivity: 'bg-green-100 text-green-700',
  test: 'bg-blue-100 text-blue-700',
  default: 'bg-gray-100 text-gray-700',
}

export const ScenarioList: FC<ScenarioListProps> = ({
  scenarios,
  onStart,
  onSelect,
  selectedId,
  filter,
}) => {
  const filteredScenarios = filter
    ? scenarios.filter(
        (s) =>
          s.name.toLowerCase().includes(filter.toLowerCase()) ||
          s.category.toLowerCase().includes(filter.toLowerCase()) ||
          s.metadata?.tags?.some((t) => t.toLowerCase().includes(filter.toLowerCase()))
      )
    : scenarios

  // Group by category
  const grouped = filteredScenarios.reduce((acc, scenario) => {
    const category = scenario.category || 'default'
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push(scenario)
    return acc
  }, {} as Record<string, Scenario[]>)

  if (scenarios.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-8 text-center">
        <p className="text-gray-500">No scenarios available</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([category, categoryScenarios]) => (
        <div key={category}>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {category}
          </h3>
          <div className="grid gap-3">
            {categoryScenarios.map((scenario) => (
              <div
                key={scenario.scenario_id}
                onClick={() => onSelect?.(scenario)}
                className={`bg-white rounded-lg border p-4 cursor-pointer transition-all ${
                  selectedId === scenario.scenario_id
                    ? 'border-blue-500 ring-2 ring-blue-100'
                    : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-semibold text-gray-900">
                        {scenario.name}
                      </h4>
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          categoryColors[scenario.category] || categoryColors.default
                        }`}
                      >
                        {scenario.category}
                      </span>
                    </div>
                    {scenario.description && (
                      <p className="text-xs text-gray-500 line-clamp-2">
                        {scenario.description}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-2">
                      <span className="text-xs text-gray-400">
                        {scenario.steps.length} steps
                      </span>
                      {scenario.metadata?.tags && (
                        <div className="flex gap-1">
                          {scenario.metadata.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="px-1.5 py-0.5 bg-gray-100 text-gray-500 text-xs rounded"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  {onStart && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onStart(scenario.scenario_id)
                      }}
                      className="px-3 py-1.5 bg-blue-500 text-white text-xs rounded-md hover:bg-blue-600 transition-colors"
                    >
                      Start
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}