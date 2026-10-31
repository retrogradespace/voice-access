# Pricing hardware

Use this when the audit shows a machine lacks a working microphone, speaker or headphones, or enough memory, and the person wants to know what fixing it would cost.

Spending money is the person's decision. Find the options, compare them and explain them. Never buy anything or enter payment details for them.

## Before pricing anything

Confirm the gap is real, because many apparent gaps cost nothing to fix:

- **Sound or microphone:** Run the audit and repeat-back checks in `SKILL.md`. The right device may be muted, or may not be the default.
- **Memory:** Measure it while the slow or failing program is running. If `talk` is the program, it already falls back from `small.en` to `base.en` to `tiny.en` when a model will not load. Smaller models need less memory but can make more transcription mistakes. If the smaller model hears the person well, they may not need to buy anything.
- **Things they already own:** Ask about phone earbuds, an old headset or a webcam, which often has a microphone. Check that the plug fits and test it first.

Then find out, in prose questions they can answer aloud:

- their total budget, and which country the item must ship to
- whether someone can plug in the device or open the computer, if the person can't
- whether other people share the room, and whether they can comfortably wear headphones
- whether they would rather spend less, or pay more for something easier to use

## Options by gap

### No microphone, speaker or headphones

Prefer wired, as `SKILL.md` explains. Look for these options in this order:

1. **Missing both microphone and sound:** a wired USB headset. One purchase fills both gaps, it plugs into one port, and wearing it prevents echo.
2. **Missing only a microphone:** a USB microphone, or a headset if the room is noisy or has speakers playing. Speakers plus an open microphone will echo.
3. **Missing only sound:** wired headphones. Use speakers only if the person has no open microphone or can't wear headphones.
4. **Can't wear a headset:** a conference speakerphone with hardware echo cancellation.

Check the fit before suggesting one:

- **Ports:** Confirm which ports are free from the manufacturer's documentation, or ask the person or a helper. Count a USB-C-only device as needing an adapter, and include the adapter in the price.
- **Audio jacks:** An `UNPLUGGED` onboard endpoint shows the jack is there and empty. A single jack on a laptop usually takes a combined headset plug, while a desktop with separate jacks may need a splitter. Confirm which from the manufacturer's documentation.
- **Hands and dexterity:** For someone with limited hand use, favor a device that works as soon as it's plugged in, with no small switches, pairing steps or app. Check whether it has a physical mute switch, because bumping one looks like a broken microphone.
- **USB microphones with a headphone socket:** Windows may make this the default output. See Pitfalls.

### Not enough memory

Don't price memory until you know what fits:

```powershell
Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, ConfiguredClockSpeed, PartNumber, BankLabel
(Get-CimInstance Win32_BaseBoard).Product
(Get-CimInstance Win32_ComputerSystem).SystemSKUNumber
```

Look up the board ID and SKU, not the marketing model name, in the manufacturer's documentation. Confirm:

- the memory type, the number of slots and the maximum supported
- whether the memory is soldered, which is common in thin laptops and means it can't be upgraded
- whether existing sticks stay in or must be replaced, since that changes how much to buy
- whether opening the computer is something the person, or someone helping, can actually do

Don't trust firmware for these answers. On OEM machines, SMBIOS data is frequently wrong. Observed on one HP desktop:

- `Win32_PhysicalMemoryArray` reported **4 DIMM slots and a 64 GB maximum**. The manufacturer's own board documentation said **2 slots, 32 GB maximum**. The WMI figure was wrong in a way that would have caused a bad purchase.
- `Win32_SystemSlot` listed the M.2 slot as `Available` while the boot SSD was plainly installed in it.
- Both memory sticks reported the same `BankLabel`.

Match the base speed, not the marketing number. On OEM boards without XMP support, a RAM kit advertised at a tighter CAS latency falls back to its slower base JEDEC speed, so the cheaper-looking faster kit can be genuinely slower on that machine.

## Getting real prices

A memory-upgrade estimate given from training knowledge was off by roughly a factor of three against live prices in a volatile market. So never quote a price from memory:

- Search live, from sellers who ship to the person's country.
- Record the price, the seller, the link and the date you checked it.
- Include delivery, tax where shown, and any adapter the option needs.
- Check that it's in stock, and whether it's new, refurbished or from a third-party marketplace seller.
- Check the return policy, since the device may not work for this person even if it works as described.
- If you can't confirm a figure, say "price not verified" rather than guessing.

## Presenting the options

Offer two or three options at most, in speakable sentences rather than a table if the person is listening. For each one, say:

- what it is, and which gap it fills
- the total price, and the date you checked it
- why it suits this machine and this person
- what could go wrong, and whether it can be returned

Then say which one you would choose and why. Include the free option if there is one.

## After it arrives

A purchase isn't finished until the person confirms it works:

- **Sound or microphone:** Run the workflow in `SKILL.md` again, including repeat-back, and check the default device didn't change.
- **Memory:** Confirm the full amount and speed appear, then run the program that was failing.

Test soon enough to return it if it fails.
