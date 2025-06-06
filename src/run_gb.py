import os
import sys
from pathlib import Path

def import_gba_modules():
    try:
        from src.emulators.gba.interface import GBAInterface
        from src.llm.realtime_agent import GameBoyAgent
        from src.evaluator import GBEvaluator
        from src.consts import ROM_FILE_MAP
        return GBAInterface, GameBoyAgent, GBEvaluator, ROM_FILE_MAP
    except ImportError as e:
        print(f"Error importing GBA modules: {e}")
        print("Make sure you have installed the required dependencies for GBA emulation.")
        sys.exit(1)

async def run_gba_emulator(args):
    """Run the GBA emulator with the given arguments."""
    # Import required modules
    GBAInterface, GameBoyAgent, GBEvaluator, ROM_FILE_MAP = import_gba_modules()
    
    # Create ROM directory if it doesn't exist
    project_root = Path(__file__).parent.parent
    rom_dir = project_root / "roms"
    rom_dir.mkdir(exist_ok=True)
    
    # Check if ROM name exists in mapping
    if args.game not in ROM_FILE_MAP:
        print(f"Unknown ROM name: {args.game}")
        print(f"Available ROMs: {', '.join(ROM_FILE_MAP.keys())}")
        return
        
    # Get full ROM path
    rom_file = ROM_FILE_MAP[args.game]
    rom_path = rom_dir / rom_file
    
    if not rom_path.exists():
        print(f"Please place the ROM file '{rom_file}' at: {rom_path}")
        print("Note: The ROM file should be an uncompressed .gb or .gbc file")
        return
        
    # Initialize game interface
    render = not args.headless
    game = GBAInterface(render=render)
    
    # Get API key from args or environment
    api_key = args.api_key

    # Set model based on API if not specified
    model = args.model
    
    # Initialize LLM interface based on chosen API and mode
    gba_agent = None
    
    if args.fake_actions:
        # Don't initialize any API if using fake actions
        print("Using fake random actions (no LLM API calls)")

    # Initialize the realtime GBAAgent
    gba_agent = GameBoyAgent(
        model=model,
        api_key=api_key,
        game=args.game,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_history_tokens=args.history_tokens,
        realtime=not args.lite,
        enable_ui=args.enable_ui,
        record=args.record,
        task_prompt=args.task_prompt,
        num_screenshots_per_action=args.num_screenshots_per_action,
        api_base=args.api_base
    )
    print(f"Using realtime agent with model: {model}")
    
    # Load the game
    print(f"Loading ROM: {rom_path}")
    if not game.load_game(str(rom_path)):
        print("Failed to load ROM")
        game.close()
        return
    
    print("Game loaded successfully!")
    if gba_agent:
        print(f"Logging to: {gba_agent.log_dir}")
    
    # Create evaluator
    print(f"Running for up to {args.max_steps} steps...")
    evaluator = GBEvaluator(
        game_interface=game, 
        max_steps=args.max_steps, 
        step_delay=args.step_delay, 
        skip_frames=args.skip_frames,
        action_frames=args.action_frames,
        fake_actions=args.fake_actions,
        checkpoints=args.checkpoints
    )
    
    try:
        if not args.lite and gba_agent:
            # Properly await the realtime evaluation instead of creating a new event loop
            metrics = await evaluator.run_episode_realtime(gba_agent)
        else:
            # Run the normal synchronous evaluation
            metrics = await evaluator.run_episode(gba_agent)
        
    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user")
    finally:
        print("Cleaning up...")
        game.close()