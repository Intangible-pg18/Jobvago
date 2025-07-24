using Jobvago.Api.Data;
using Jobvago.Api.Models;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Jobvago.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class JobsController : ControllerBase
{
    private readonly JobvagoDbContext _context;
    
    public JobsController(JobvagoDbContext context)
    {
        _context = context;
    }

    [HttpGet]
    public async Task<ActionResult<IEnumerable<Job>>> GetJobs()
    {
        var jobs = await _context.Jobs.Include(j => j.Company).ToListAsync();
        return Ok(jobs);
    }
}