"use client";

import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Self-hosted worker — avoids CDN dependency and works in restricted networks
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface PdfViewerProps {
    file: string;
    onError: () => void;
}

export default function PdfViewer({ file, onError }: PdfViewerProps) {
    return (
        <Document
            file={file}
            onLoadError={onError}
            loading={
                <div className="flex items-center justify-center h-48 text-xs text-muted-foreground">
                    Loading PDF...
                </div>
            }
        >
            <Page pageNumber={1} width={380} />
        </Document>
    );
}
