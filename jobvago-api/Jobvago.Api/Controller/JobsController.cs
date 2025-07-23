using Jobvago.Api.Data;
using Jobvago.Api.Models;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Jobvago.Api.Controllers;

[ApiController]
[Route("api/[controller]")] // This means the URL will be /api/jobs
public class JobsController : ControllerBase
{
    private readonly JobvagoDbContext _context;

    // The DbContext is "injected" here by the framework. We don't create it!
    public JobsController(JobvagoDbContext context)
    {
        _context = context;
    }

    // Handles GET requests to /api/jobs
    [HttpGet]
    public async Task<ActionResult<IEnumerable<Job>>> GetJobs()
    {
        // Use EF Core to get all jobs from the database asynchronously.
        // EF Core translates this into "SELECT * FROM Jobs"
        var jobs = await _context.Jobs.Include(j => j.Company).ToListAsync();
        return Ok(jobs); // Return a 200 OK with the list of jobs as JSON
    }
}