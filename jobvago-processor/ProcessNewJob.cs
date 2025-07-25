using System;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Azure.Functions.Worker;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Jobvago.Api.Data;
using Jobvago.Api.Models;

namespace Jobvago.Processor;

public class ProcessNewJob
{
    private readonly ILogger<ProcessNewJob> _logger;
    private readonly JobvagoDbContext _context; 

    public ProcessNewJob(ILogger<ProcessNewJob> logger, JobvagoDbContext context)
    {
        _logger = logger;
        _context = context;
    }

    [Function(nameof(ProcessNewJob))]
    public async Task Run([ServiceBusTrigger("new-jobs-queue", Connection = "ServiceBusConnectionString")] string myQueueItem)
    {
        _logger.LogInformation("C# ServiceBus queue trigger function started processing a message.");

        // Step 1: Deserialize the incoming JSON message into our DTO
        JobItemDto? rawJob;
        try
        {
            rawJob = JsonSerializer.Deserialize<JobItemDto>(myQueueItem);
            if (rawJob == null || string.IsNullOrWhiteSpace(rawJob.OriginalUrl))
            {
                _logger.LogError("Failed to deserialize message or message is invalid: {message}", myQueueItem);
                return; 
            }
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "JSON Deserialization failed for message: {message}", myQueueItem);
            return; 
        }

        _logger.LogInformation("Processing job: '{JobTitle}' from '{Company}'", rawJob.Title, rawJob.CompanyName);

        // Step 2: Begin a database transaction
        await using var transaction = await _context.Database.BeginTransactionAsync();
        try
        {
            // Step 3: Check if this job already exists by its unique URL
            var existingJob = await _context.Jobs.FirstOrDefaultAsync(j => j.OriginalUrl == rawJob.OriginalUrl);
            if (existingJob != null)
            {
                // If the job exists, we can update its "LastSeenAt" timestamp and stop.
                _logger.LogWarning("Job with URL '{url}' already exists. Updating timestamp.", rawJob.OriginalUrl);
                existingJob.LastSeenAt = DateTime.UtcNow;
                await _context.SaveChangesAsync();
                await transaction.CommitAsync();
                return;
            }

            // Step 4: Perform "Get-or-Create" for related data (Company and Source)
            var company = await GetOrCreateEntityAsync(_context.Companies, c => c.Name == rawJob.CompanyName, new Company { Name = rawJob.CompanyName });
            var source = await GetOrCreateEntityAsync(_context.Sources, s => s.Name == rawJob.Source, new Source { Name = rawJob.Source });

            // Step 5: Create the new Job entity and populate it
            var newJob = new Job
            {
                JobTitle = rawJob.Title,
                OriginalUrl = rawJob.OriginalUrl,
                CompanyID = company.ID, 
                SourceID = source.ID,  
                CreatedAt = DateTime.UtcNow,
                LastSeenAt = DateTime.UtcNow
                // We will add salary/location parsing logic here later.
            };

            // Step 6: Add the new job and save everything
            _context.Jobs.Add(newJob);
            await _context.SaveChangesAsync();

            // Step 7: If all operations were successful, commit the transaction
            await transaction.CommitAsync();
            _logger.LogInformation("Successfully processed and saved new job with ID: {JobId}", newJob.ID);
        }
        catch (Exception ex)
        {
            // Step 8: If any error occurred, roll back the entire transaction
            _logger.LogError(ex, "An error occurred during database processing. Rolling back transaction.");
            await transaction.RollbackAsync();
            throw;
        }
    }
    
    private async Task<T> GetOrCreateEntityAsync<T>(DbSet<T> dbSet, System.Linq.Expressions.Expression<Func<T, bool>> predicate, T newEntity) where T : class
    {
        var entity = await dbSet.FirstOrDefaultAsync(predicate);
        if (entity == null)
        {
            entity = newEntity;
            dbSet.Add(entity);
            await _context.SaveChangesAsync();
        }
        return entity;
    }
}