import { useCallback, useRef, useState, type DragEvent, type ChangeEvent } from 'react';
import { Upload, FileText, CheckCircle, AlertTriangle, X } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '../atoms/Card';
import { Button } from '../atoms/Button';
import { Badge } from '../atoms/Badge';
import { Spinner } from '../atoms/Spinner';
import { AlertBanner } from '../molecules/AlertBanner';
import { InvoiceFieldRow } from '../molecules/InvoiceFieldRow';
import { extractInvoice } from '../../api/invoices';
import { formatTHB } from '../../utils/currency';
import { formatDate } from '../../utils/dates';
import type { InvoiceExtractResponse } from '../../types/invoice';

const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
const ACCEPTED_EXTENSIONS = '.pdf,.jpg,.jpeg,.png';
const CONFIDENCE_THRESHOLD = 0.85;

export function InvoiceUpload() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<InvoiceExtractResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});

  const reset = () => {
    setSelectedFile(null);
    setResult(null);
    setError(null);
    setEditedFields({});
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFile = (file: File) => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError('Unsupported file type. Please upload a PDF, JPG, or PNG.');
      return;
    }
    setError(null);
    setResult(null);
    setSelectedFile(file);
  };

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, []);

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);
    try {
      const data = await extractInvoice(selectedFile);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Extraction failed. Please upload a clearer image.',
      );
    } finally {
      setUploading(false);
    }
  };

  const handleFieldChange = (key: string, value: string) => {
    setEditedFields((prev) => ({ ...prev, [key]: value }));
  };

  const needsReview = result && result.confidence < CONFIDENCE_THRESHOLD;
  const fields = result?.extracted_fields;
  const fieldConfidences = result?.field_confidences ?? {};

  const getFieldValue = (key: string, raw: string | number | undefined) => {
    if (editedFields[key] !== undefined) return editedFields[key];
    if (raw === undefined || raw === null) return '—';
    if (typeof raw === 'number') {
      if (key === 'amount_thb' || key === 'amount_paid_thb') return formatTHB(raw);
      return String(raw);
    }
    if (key === 'due_date' || key === 'issue_date') return formatDate(raw as string);
    return String(raw);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Invoice</CardTitle>
        {result && (
          <Button variant="ghost" size="sm" onClick={reset} aria-label="Clear and upload new">
            <X className="h-4 w-4" aria-hidden="true" />
            Clear
          </Button>
        )}
      </CardHeader>

      {/* Drop zone */}
      {!result && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
            ${dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Click or drag to upload invoice"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            className="hidden"
            onChange={handleFileInput}
            aria-label="Invoice file input"
          />
          <Upload className="h-10 w-10 text-gray-300 mx-auto mb-3" aria-hidden="true" />
          <p className="text-sm font-medium text-gray-700 mb-1">
            Drag & drop or click to upload
          </p>
          <p className="text-xs text-gray-400">PDF, JPG, or PNG — max 10 MB</p>

          {selectedFile && (
            <div className="mt-4 flex items-center justify-center gap-2 text-sm text-blue-700 bg-blue-50 px-3 py-2 rounded-lg">
              <FileText className="h-4 w-4" aria-hidden="true" />
              <span className="font-medium truncate max-w-48">{selectedFile.name}</span>
            </div>
          )}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-4">
          <AlertBanner
            variant="danger"
            title="Upload Error"
            message={error}
          />
        </div>
      )}

      {/* Upload button */}
      {selectedFile && !result && !uploading && (
        <Button variant="primary" className="w-full mt-4" onClick={handleUpload}>
          Extract Invoice Fields
        </Button>
      )}

      {/* Uploading spinner */}
      {uploading && (
        <div className="flex items-center justify-center py-8">
          <Spinner label="Extracting invoice fields..." />
        </div>
      )}

      {/* Result */}
      {result && fields && (
        <div className="mt-2">
          {/* Confidence banner */}
          {needsReview ? (
            <AlertBanner
              variant="warning"
              title="Needs Review"
              message="Some fields have low confidence. Please review and correct highlighted fields before confirming."
              className="mb-4"
            />
          ) : (
            <div className="flex items-center gap-2 mb-4 p-3 bg-green-50 rounded-lg border border-green-100">
              <CheckCircle className="h-5 w-5 text-green-600" aria-hidden="true" />
              <div>
                <p className="text-sm font-semibold text-green-800">Auto-recorded</p>
                <p className="text-xs text-green-600">High-confidence extraction. Invoice saved.</p>
              </div>
            </div>
          )}

          {/* Direction + summary */}
          <div className="flex items-center gap-2 mb-4">
            <Badge variant={result.direction === 'receivable' ? 'success' : 'info'}>
              {result.direction === 'receivable' ? 'Receivable' : 'Payable'}
            </Badge>
            {result.record_id && (
              <span className="text-xs text-gray-400">ID: {result.record_id}</span>
            )}
          </div>

          {/* Fields grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
            <InvoiceFieldRow
              label="Invoice No."
              value={getFieldValue('invoice_no', fields.invoice_no)}
              fieldKey="invoice_no"
              confidence={fieldConfidences['invoice_no']}
              editable={!!needsReview}
              onChange={handleFieldChange}
            />
            <InvoiceFieldRow
              label="Counterparty"
              value={getFieldValue('counterparty_name', fields.counterparty_name)}
              fieldKey="counterparty_name"
              confidence={fieldConfidences['counterparty_name']}
              editable={!!needsReview}
              onChange={handleFieldChange}
            />
            <InvoiceFieldRow
              label="Amount"
              value={getFieldValue('amount_thb', fields.amount_thb)}
              fieldKey="amount_thb"
              confidence={fieldConfidences['amount_thb']}
              editable={!!needsReview}
              onChange={handleFieldChange}
            />
            <InvoiceFieldRow
              label="Due Date"
              value={getFieldValue('due_date', fields.due_date)}
              fieldKey="due_date"
              confidence={fieldConfidences['due_date']}
              editable={!!needsReview}
              onChange={handleFieldChange}
            />
            {fields.issue_date && (
              <InvoiceFieldRow
                label="Issue Date"
                value={getFieldValue('issue_date', fields.issue_date)}
                fieldKey="issue_date"
                confidence={fieldConfidences['issue_date']}
                editable={!!needsReview}
                onChange={handleFieldChange}
              />
            )}
            {result.direction === 'receivable' && fields.customer_email && (
              <InvoiceFieldRow
                label="Customer Email"
                value={getFieldValue('customer_email', fields.customer_email)}
                fieldKey="customer_email"
                confidence={fieldConfidences['customer_email']}
                editable={!!needsReview}
                onChange={handleFieldChange}
              />
            )}
            {fields.amount_paid_thb !== undefined && fields.amount_paid_thb > 0 && (
              <InvoiceFieldRow
                label="Amount Paid"
                value={getFieldValue('amount_paid_thb', fields.amount_paid_thb)}
                fieldKey="amount_paid_thb"
                confidence={fieldConfidences['amount_paid_thb']}
                editable={!!needsReview}
                onChange={handleFieldChange}
              />
            )}
          </div>

          {/* Confirm & Record button for low-confidence */}
          {needsReview && (
            <Button variant="primary" className="w-full">
              <CheckCircle className="h-4 w-4" aria-hidden="true" />
              Confirm & Record
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
