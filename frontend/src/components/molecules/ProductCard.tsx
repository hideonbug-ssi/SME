import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, CheckCircle } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '../atoms/Card';
import { Button } from '../atoms/Button';
import { Badge } from '../atoms/Badge';
import type { ProductRecommendation } from '../../types/recommendation';

interface ProductCardProps {
  recommendation: ProductRecommendation;
  onLearnMore?: () => void;
}

export function ProductCard({ recommendation, onLearnMore }: ProductCardProps) {
  const [disclosuresOpen, setDisclosuresOpen] = useState(false);
  const relevancePct = Math.round(recommendation.relevance_score * 100);

  const handleLearnMore = () => {
    if (onLearnMore) {
      onLearnMore();
    } else {
      // PoC: show toast-style feedback via console
      alert('This feature is coming soon. Please contact your KTB relationship manager.');
    }
  };

  return (
    <Card className="border-blue-100 bg-gradient-to-br from-white to-blue-50">
      <CardHeader>
        <div>
          <p className="text-xs font-medium text-blue-600 uppercase tracking-wide mb-1">
            Recommended for You
          </p>
          <CardTitle className="text-gray-900">{recommendation.product_name}</CardTitle>
        </div>
        {recommendation.repayability === 'passed' && (
          <div className="flex items-center gap-1 text-green-700 text-xs font-medium">
            <CheckCircle className="h-4 w-4" aria-hidden="true" />
            <span>Repayability confirmed</span>
          </div>
        )}
      </CardHeader>

      <p className="text-sm text-gray-700 mb-4 leading-relaxed">{recommendation.rationale}</p>

      {/* Relevance score bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Relevance match</span>
          <span className="font-medium text-gray-700">{relevancePct}%</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${relevancePct}%` }}
            role="progressbar"
            aria-valuenow={relevancePct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <Badge variant="gray" className="text-xs">
          Based on: {recommendation.signal_basis}
        </Badge>
      </div>

      {/* Disclosures collapsible */}
      {(recommendation.disclosures ?? []).length > 0 && (
        <div className="mb-4">
          <button
            onClick={() => setDisclosuresOpen((o) => !o)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
            aria-expanded={disclosuresOpen}
          >
            {disclosuresOpen ? (
              <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {disclosuresOpen ? 'Hide' : 'View'} disclosures
          </button>
          {disclosuresOpen && (
            <ul className="mt-2 space-y-1">
              {recommendation.disclosures.map((d, i) => (
                <li key={i} className="text-xs text-gray-500 pl-2 border-l border-gray-200">
                  {d}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Button
        variant="primary"
        size="sm"
        onClick={handleLearnMore}
        className="w-full"
      >
        <ExternalLink className="h-4 w-4" aria-hidden="true" />
        Learn More
      </Button>
    </Card>
  );
}
