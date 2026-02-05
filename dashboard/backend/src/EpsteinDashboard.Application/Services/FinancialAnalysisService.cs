using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;

namespace EpsteinDashboard.Application.Services;

public class FinancialAnalysisService
{
    private readonly IFinancialTransactionRepository _repository;
    private readonly IMapper _mapper;

    public FinancialAnalysisService(IFinancialTransactionRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    public async Task<FinancialFlowDto> GetFlowsAsync(CancellationToken cancellationToken = default)
    {
        var flows = await _repository.GetFlowsAsync(cancellationToken);
        return _mapper.Map<FinancialFlowDto>(flows);
    }

    public async Task<FinancialSummary> GetSummaryAsync(CancellationToken cancellationToken = default)
    {
        return await _repository.GetSummaryAsync(cancellationToken);
    }
}
