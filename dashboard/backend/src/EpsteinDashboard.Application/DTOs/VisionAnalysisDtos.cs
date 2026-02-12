namespace EpsteinDashboard.Application.DTOs;

public record FaceDetectionDto(
    long FaceId,
    long MediaFileId,
    string? MediaFilePath,
    int FaceIndex,
    string? BoundingBox,
    long? ClusterId,
    string? ClusterName,
    double? Confidence,
    DateTime CreatedAt
);

public record FaceClusterDto(
    long ClusterId,
    string? PersonName,
    long? PersonId,
    int FaceCount,
    long? RepresentativeFaceId,
    string? RepresentativeImagePath,
    DateTime CreatedAt
);

public record FaceClusterDetailDto(
    long ClusterId,
    string? PersonName,
    long? PersonId,
    int FaceCount,
    IReadOnlyList<FaceDetectionDto> Faces,
    DateTime CreatedAt
);

public record DocumentClassificationDto(
    long ClassificationId,
    long MediaFileId,
    string? MediaFilePath,
    bool IsDocument,
    bool IsPhoto,
    string? DocumentType,
    string? DocumentSubtype,
    bool HasHandwriting,
    bool HasSignature,
    bool HasLetterhead,
    bool HasStamp,
    double? TextDensity,
    double? Confidence,
    DateTime CreatedAt
);

public record VisionAnalysisStatsDto(
    int TotalImages,
    int TotalFaceDetections,
    int TotalFaceClusters,
    int TotalClassifications,
    int DocumentCount,
    int PhotoCount,
    int WithHandwriting,
    int WithSignatures,
    IReadOnlyList<DocumentTypeCountDto> DocumentTypeCounts
);

public record DocumentTypeCountDto(
    string DocumentType,
    int Count
);

public record ImportStatusDto(
    int TotalDocuments,
    int ExpectedDocuments,
    int TotalMediaFiles,
    int TotalPages,
    long TotalSizeBytes,
    string? LastEftaNumber,
    string? LastFilePath,
    string? LastUpdated,
    Dictionary<string, int> ExtractionStats,
    int DocumentsWithText,
    int DocumentsNeedingOcr,
    int TotalDocsWithImages
);
